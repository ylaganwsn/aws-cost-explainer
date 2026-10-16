resource "aws_sns_topic" "reports" {
  name = "${var.project_name}-reports"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.reports.arn
  protocol  = "email"
  endpoint  = var.notification_email
}