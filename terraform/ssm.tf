resource "aws_ssm_parameter" "gemini_key" {
  name             = var.gemini_key_parameter_name
  description      = "Gemini API key for ${var.project_name}"
  type             = "SecureString"
  value_wo         = var.gemini_api_key
  value_wo_version = 1
}