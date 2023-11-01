exports.handler = async (event) => {
  let body;
  let statusCode = 200;
  const headers = {
    "Content-Type": "application/json",
  };
  try {
    let bodyJSON = JSON.parse(event.detail.body);
    console.log(`INFO: Logging message body to console...`);
    console.log(bodyJSON);
  } catch (err) {
    console.log(err);
    statusCode = 400;
    body = err.message;
  } finally {
    body = JSON.stringify(body);
  }
  return {
    statusCode,
    body,
    headers,
  };
};
