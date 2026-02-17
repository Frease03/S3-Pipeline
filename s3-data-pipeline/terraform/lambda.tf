# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for Lambda to access S3 and CloudWatch
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${local.name_prefix}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.raw.arn,
          "${aws_s3_bucket.raw.arn}/*",
          aws_s3_bucket.processed.arn,
          "${aws_s3_bucket.processed.arn}/*",
          aws_s3_bucket.archive.arn,
          "${aws_s3_bucket.archive.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          aws_sqs_queue.processing_queue.arn,
          aws_sqs_queue.dlq.arn
        ]
      }
    ]
  })
}

# Data Processor Lambda Function
resource "aws_lambda_function" "data_processor" {
  filename         = "${path.module}/../lambda/data_processor.zip"
  function_name    = "${local.name_prefix}-data-processor"
  role             = aws_iam_role.lambda_role.arn
  handler          = "data_processor.handler"
  source_code_hash = filebase64sha256("${path.module}/../lambda/data_processor.zip")
  runtime          = "python3.11"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size

  environment {
    variables = {
      RAW_BUCKET       = aws_s3_bucket.raw.id
      PROCESSED_BUCKET = aws_s3_bucket.processed.id
      ARCHIVE_BUCKET   = aws_s3_bucket.archive.id
      ENVIRONMENT      = var.environment
    }
  }
}

# Permission for S3 to invoke Lambda
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.raw.arn
}

# Data Archiver Lambda Function
resource "aws_lambda_function" "data_archiver" {
  filename         = "${path.module}/../lambda/data_archiver.zip"
  function_name    = "${local.name_prefix}-data-archiver"
  role             = aws_iam_role.lambda_role.arn
  handler          = "data_archiver.handler"
  source_code_hash = filebase64sha256("${path.module}/../lambda/data_archiver.zip")
  runtime          = "python3.11"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size

  environment {
    variables = {
      PROCESSED_BUCKET = aws_s3_bucket.processed.id
      ARCHIVE_BUCKET   = aws_s3_bucket.archive.id
      RETENTION_DAYS   = tostring(var.retention_days)
    }
  }
}

# CloudWatch Event Rule to trigger archiver daily
resource "aws_cloudwatch_event_rule" "daily_archive" {
  name                = "${local.name_prefix}-daily-archive"
  description         = "Trigger data archiver daily"
  schedule_expression = "cron(0 2 * * ? *)" # 2 AM UTC daily
}

resource "aws_cloudwatch_event_target" "archive_lambda" {
  rule      = aws_cloudwatch_event_rule.daily_archive.name
  target_id = "DataArchiver"
  arn       = aws_lambda_function.data_archiver.arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowCloudWatchInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_archiver.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_archive.arn
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "processor_logs" {
  name              = "/aws/lambda/${aws_lambda_function.data_processor.function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "archiver_logs" {
  name              = "/aws/lambda/${aws_lambda_function.data_archiver.function_name}"
  retention_in_days = 14
}
