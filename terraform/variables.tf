variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used to name all resources"
  type        = string
  default     = "aws-cost-explainer"
}

variable "notification_email" {
  description = "Email address that receives the weekly report"
  type        = string
}

variable "gemini_key_parameter_name" {
  description = "Name of the SSM SecureString parameter that holds the Gemini API key"
  type        = string
  default     = "/aws-cost-explainer/gemini-api-key"
}