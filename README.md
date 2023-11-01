# Amazon Serverless Immutable Transaction Pipeline

This pattern will accelerate the deployment of an Asynchronous, event-driven, immutable transaction pipeline, built on [AWS Serverless](https://aws.amazon.com/serverless/) services. The provided configuration of [Amazon Simple Queue Service](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html) and [Amazon EventBridge](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html), ensures that the payload is not manipulated in transit, whilst preserving a copy of each event in an archive (so events can be replayed through the system if required.) This pattern is intended to bootstrap many of the required components, so that you can focus on building the business logic that differentiates your workload. In this example, an [AWS Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html) Express Workflow is configured to invoke an [AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html) function that will print the payload to [Amazon CloudWatch](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/WhatIsCloudWatch.html) Logs. Customising this workflow to suit your requirements is the recommended place to start. For example, you could perform request validation with an additional [AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html) function, or store the payload in an [Amazon DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html) table. 

Important: this application uses various AWS services and there are costs associated with these services after the Free Tier usage - please see the [AWS Pricing page](https://aws.amazon.com/pricing/) for details. You are responsible for any AWS costs incurred. No warranty is implied in this example.

## Requirements

* [Create an AWS account](https://portal.aws.amazon.com/gp/aws/developer/registration/index.html) if you do not already have one and log in. The IAM user that you use must have sufficient permissions to make necessary AWS service calls and manage AWS resources.
* [Bootstrap](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html#bootstrapping-howto) your account to prepare for CDK deployments
* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) installed and configured
* [Git Installed](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
* [AWS CDK Toolkit](https://docs.aws.amazon.com/cdk/latest/guide/cli.html) installed and configured
* [Python 3.9+](https://www.python.org/downloads/) installed

## Deployment Instructions

1. Create a new directory, navigate to that directory in a terminal and clone the GitHub repository:
    ```
    git clone https://github.com/aws-samples/serverless-immutable-transaction-pipeline
    ```
2. Change directory to the pattern directory:
    ```
    cd serverless-immutable-transaction-pipeline
    ```
3. Create a virtual environment for Python
    ```
    python3 -m venv .venv
    ```
4. Activate the virtual environment
    ```
    source .venv/bin/activate
    ```
    For a Windows platform, activate the virtualenv like this:
    ```
    .venv\Scripts\activate.bat
    ```
5. Install the Python required dependencies:
    ```
    pip3 install -r requirements.txt
    ```
6. From the command line, use AWS CDK to deploy the AWS resources for the serverless application as specified in the app.py file:
    ```
    cdk deploy MyServerlessApplicationStack
    ```
7. Note the outputs from the CDK deployment process. These contain the API Gateway Endpoint which is used for testing.

## How it works

A test payload is sent from the client (CLI) to invoke an [Amazon API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html) HTTP API endpoint that integrates with an Amazon SQS Queue. The payload is stored in the Amazon SQS Queue as a message. Amazon EventBridge Pipes acts as a consumer of the Amazon SQS Queue, messages are pulled from the queue and [Amazon EventBridge Pipes](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-pipes.html) routes events to an Amazon EventBridge event bus. A rule is configured in the Amazon EventBridge event bus to forward events from Amazon EventBridge Pipes to an [AWS Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html) Express Workflow. A simple workflow is configured to invoke an [AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html) function that will print the payload to [Amazon CloudWatch](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/WhatIsCloudWatch.html) Logs.

Additionally, an Archive is configed for the Amazon EventBridge event bus for a period of 7 days. This ensures events that transit the event bus can be replayed through the pipeline. 

## Testing

From the command line, run the following command to send an HTTP `POST` request to the API endpoint. Note that you must utilise the provided Amazon API Gateway HTTP endpoint. This is listed as output in the MyServerlessApplicationStack deployment outputs.

```
curl -d '{"key1":"value1", "key2":"value2"}' -H "Content-Type: application/json" -X POST {MyServerlessApplicationStack.ApiEndpoint}
```
You can review the Amazon CloudWatch Logs, Log Group to find the exmple message printed to the log. When you run the above command more than once you should see the additional logs streamed to the Log Group once they have transited through the pipeline. 

You can also replay test events through the system by following the process here - [Replaying archived Amazon EventBridge events](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-replay-archived-event.html)

## Cleanup

1. Delete the stack
    ```
    cdk destroy MyServerlessApplicationStack
    ```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file. st