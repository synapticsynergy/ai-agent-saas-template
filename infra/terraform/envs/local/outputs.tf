output "storage_bucket_name" {
  value = module.storage.bucket_name
}

output "dynamodb_table_name" {
  value = module.storage.dynamodb_table_name
}
