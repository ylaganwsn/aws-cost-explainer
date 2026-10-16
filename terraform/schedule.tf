resource "aws_cloudwatch_event_rule" "weekly" {
  name                = "${var.project_name}-weekly"
  description         = "Triggers the weekly AWS cost report"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule = aws_cloudwatch_event_rule.weekly.name
  arn  = aws_lambda_function.report.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.report.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly.arn
}