# Registers the address with SES. AWS emails a one-time verification link to it.
# In the SES sandbox both sender and recipient must be verified; this one address is both.
resource "aws_sesv2_email_identity" "report" {
  email_identity = var.notification_email
}
