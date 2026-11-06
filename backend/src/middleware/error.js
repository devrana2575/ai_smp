const errorHandler = (err, req, res, _next) => {
  const statusCode = err.statusCode || 500;
  const production = process.env.NODE_ENV === "production";
  const requestId = req.id || "unknown";

  // Log structured context without request bodies, headers, or secrets.
  console.error(
    JSON.stringify({
      level: "error",
      requestId,
      method: req.method,
      path: req.originalUrl,
      statusCode,
      message: err.message,
      ...(production ? {} : { stack: err.stack }),
    })
  );

  const clientMessage =
    statusCode >= 500 ? "Internal server error" : err.message;

  res.status(statusCode).json({
    detail: clientMessage,
    requestId,
    ...(!production && { stack: err.stack }),
  });
};

module.exports = errorHandler;
