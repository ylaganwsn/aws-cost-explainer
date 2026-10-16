output "function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.report.function_name
}

output "sns_topic_arn" {
  description = "SNS topic the report is published to"
  value       = aws_sns_topic.reports.arn
}

output "log_group" {
  description = "CloudWatch log group with the function's logs"
  value       = aws_cloudwatch_log_group.lambda.name
}

output "schedule" {
  description = "When the report runs (UTC)"
  value       = aws_cloudwatch_event_rule.weekly.schedule_expression
}