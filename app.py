#!/usr/bin/env python3
import os
import json
from aws_cdk import (
    Aws,
    App,
    Stack,
    Environment,
    CfnOutput,
    Duration,
    Tags,
    aws_sqs as sqs,
    aws_iam as iam,
    aws_apigatewayv2 as apigatewayv2,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_stepfunctions_tasks as tasks,
    aws_stepfunctions as sfn,
    aws_events as events,
    aws_pipes as pipes,
    aws_events_targets as targets
)
from constructs import Construct

deployment_account_id = Aws.ACCOUNT_ID
deployment_region = Aws.REGION

DIRNAME = os.path.dirname(__file__)

class MyServerlessApplicationStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Environment variables used for constructing eventbridge rule
        region = Stack.of(self).region
        account = Stack.of(self).account

        # Tag all resources in the stack to prevent them from being deleted
        Tags.of(self).add("auto-delete", "no")

        # create the sqs deadletter queue
        dlqueue = sqs.Queue(
            self, "sitp-cdk-dl-queue",
            visibility_timeout=Duration.seconds(300),
            queue_name="sitp-cdk-dl-queue",
            enforce_ssl=True
        )

        # create the sqs queue
        queue = sqs.Queue(
            self, "sitp-cdk-queue",
            visibility_timeout=Duration.seconds(300),
            queue_name="sitp-cdk-queue",
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=123,
                queue=dlqueue
            ),
            enforce_ssl=True
        )

        # Create an IAM Role for API Gateway
        role = iam.Role(self, "api-gateway-role",
                        assumed_by=iam.ServicePrincipal(
                            "apigateway.amazonaws.com"),
                        description="This role allows API Gateway to send messages to SQS queue",
                        role_name="api-gateway-send-to-sqs-role"
                        )

        # Attach a policy to the role to allow sending messages to the SQS queue
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sqs:SendMessage"],
                resources=[queue.queue_arn],
            )
        )

        # Create the HTTP api which will front SQS
        api = apigatewayv2.CfnApi(self, "sitp-cdk-api",
                                  name="sitp-cdk-api",
                                  protocol_type="HTTP",
                                  )

        api_integration = apigatewayv2.CfnIntegration(self, "sitp-cdk-api-integration",
                                                      api_id=api.ref,
                                                      credentials_arn=role.role_arn,
                                                      integration_type="AWS_PROXY",
                                                      integration_subtype="SQS-SendMessage",
                                                      request_parameters={
                                                          "MessageBody": "$request.body",
                                                          "QueueUrl": queue.queue_url
                                                      },
                                                      payload_format_version="1.0"
                                                      )

        api_route = apigatewayv2.CfnRoute(self, "sitp-cdk-api-route",
                                          api_id=api.ref,
                                          route_key="POST /",
                                          target="integrations/"+api_integration.ref
                                          )

        api_log_group = logs.LogGroup(self, "sitp-cdk-api-logs")

        api_stage = apigatewayv2.CfnStage(self, "sitp-cdk-api-stage",
                                          api_id=api.ref,
                                          stage_name="$default",
                                          auto_deploy=True,
                                          access_log_settings=apigatewayv2.CfnStage.AccessLogSettingsProperty(
                                              destination_arn=api_log_group.log_group_arn,
                                              format="$context.requestId"
                                          ),
                                          )

        # Create an IAM Role for Lambda
        lambda_role = iam.Role(self, "lambda-role",
                               assumed_by=iam.ServicePrincipal(
                                   "lambda.amazonaws.com"),
                               description="This role allows lambda to store logs",
                               role_name="lambda-store-logs-role"
                               )

        # Attach a policy to the role
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"],
                resources=["*"],
            )
        )

        # Create Lambda function for state machine
        lambda_name = "sitp-cdk-lambda"
        lambda_function = _lambda.Function(self, "sitp-cdk-lambda",
                                           function_name=lambda_name,
                                           runtime=_lambda.Runtime.NODEJS_18_X,
                                           handler="index.handler",
                                           code=_lambda.Code.from_asset(
                                               os.path.join(DIRNAME, "src/lambda")),
                                           role=lambda_role
                                           )

        # Create an IAM Role for Step Functions
        state_machine_role = iam.Role(self, "step-functions-role",
                                      assumed_by=iam.ServicePrincipal(
                                          "states.amazonaws.com"),
                                      description="This role allows Step Functions to invoke lambda",
                                      role_name="step-functions-invoke-lambda-role"
                                      )

        # Attach a policy to the role to allowing lambda invocation
        state_machine_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[lambda_function.function_arn],
            )
        )

        state_machine_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogDelivery",
                         "logs:GetLogDelivery",
                         "logs:UpdateLogDelivery",
                         "logs:DeleteLogDelivery",
                         "logs:ListLogDeliveries",
                         "logs:PutResourcePolicy",
                         "logs:DescribeResourcePolicies",
                         "logs:DescribeLogGroups"],
                resources=["*"],
            )
        )

        state_machine_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["xray:PutTraceSegments",
                         "xray:PutTelemetryRecords",
                         "xray:GetSamplingRules",
                         "xray:GetSamplingTargets"],
                resources=["*"],
            )
        )

        # Create state machine
        state_machine_log_group = logs.LogGroup(self, "sitp-cdk-state-machine-logs",
                                                retention=logs.RetentionDays.FIVE_DAYS
                                                )

        invoke_lambda = tasks.LambdaInvoke(self, "Invoke with state input",
            lambda_function=lambda_function
        )
        definition = invoke_lambda

        state_machine = sfn.StateMachine(self, "sitp-cdk-state-machine",
                                         state_machine_name="sitp-cdk-state-machine",
                                         role=state_machine_role,
                                         state_machine_type=sfn.StateMachineType.EXPRESS,
                                         definition_body=sfn.DefinitionBody.from_chainable(
                                             definition),
                                         timeout=Duration.minutes(5),
                                         logs=sfn.LogOptions(
                                             destination=state_machine_log_group,
                                             level=sfn.LogLevel.ALL
                                         ),
                                         tracing_enabled=True
                                         )

        # Create EventBridge Bus amd Archive
        eventbridge_bus = events.EventBus(self, "sitp-cdk-bus",
                                          event_bus_name="sitp-cdk-bus"
                                          )

        eventbridge_bus.archive("sitp-cdk-bus-archive",
                                archive_name="sitp-cdk-bus-archive",
                                description="sitp-cdk-bus-archive",
                                event_pattern=events.EventPattern(
                                    account=[Stack.of(self).account]
                                ),
                                retention=Duration.days(7)
                                )

        # Create EventBridge Pipe
        eventbridge_pipe_role = iam.Role(self, "eventbridge-pipe-role",
                                         assumed_by=iam.ServicePrincipal(
                                             "pipes.amazonaws.com"),
                                         description="This role allows eventbridge to interact with SQS and EventBridge",
                                         role_name="eventbridge-sqs-to-eventbridge-role"
                                         )

        eventbridge_pipe_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sqs:ReceiveMessage",
                         "sqs:DeleteMessage",
                         "sqs:GetQueueAttributes"],
                resources=[queue.queue_arn],
            )
        )

        eventbridge_pipe_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:PutEvents"],
                resources=[eventbridge_bus.event_bus_arn],
            )
        )

        eventbridge_pipe = pipes.CfnPipe(self, "sitp-cdk-eventbridge-pipe",
                                         name="sitp-cdk-eventbridge-pipe",
                                         role_arn=eventbridge_pipe_role.role_arn,
                                         source=queue.queue_arn,
                                         target=eventbridge_bus.event_bus_arn,
                                         )

        # Create EventBridge Rule
        eventbridge_rule = events.Rule(self, "sitp-cdk-rule",
                                       rule_name="send-to-step-functions",
                                       event_bus=eventbridge_bus,
                                       event_pattern=events.EventPattern(
                                           source=[
                                               "Pipe " + eventbridge_pipe.name],
                                           detail_type=["Event from aws:sqs"],
                                           region=[region],
                                           account=[account]
                                       ),
                                       targets=[
                                           targets.SfnStateMachine(state_machine)]
                                       )

        # Outputs
        CfnOutput(self, "ApiEndpoint", export_name="MyApiEndpoint",
                  value=api.attr_api_endpoint)

app = App()
MyServerlessApplicationStack(app, "MyServerlessApplicationStack", env=Environment(
    account=deployment_account_id, region=deployment_region))
app.synth()