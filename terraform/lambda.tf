# 1. Zip the Python package. Lambda runs "cost_explainer.handler.handler" from this zip.
data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/build/cost_explainer.zip"
  excludes    = ["cost_explainer.egg-info", "cost_explainer/__pycache__"]
}

# 2. Log group, created here so we control how long logs are kept.
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 14
}

# 3. The function itself.
resource "aws_lambda_function" "report" {
  function_name    = local.function_name
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "cost_explainer.handler.handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 60
  memory_size      = 256

  environment {
    variables = {
      SNS_TOPIC_ARN        = aws_sns_topic.reports.arn
      GEMINI_KEY_PARAMETER = var.gemini_key_parameter_name
      USE_LLM              = tostring(var.use_llm)
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy.lambda,
  ]
}