-- MySQL/MariaDB Database Setup Script
-- This script creates the database and user for the citizen affiliation service

-- Create database with UTF-8 support
CREATE DATABASE IF NOT EXISTS citizen_affiliation 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

-- Create user with password
-- IMPORTANT: Change 'djangopass' to a secure password in production!
CREATE USER IF NOT EXISTS 'djangouser'@'localhost' IDENTIFIED BY 'djangopass';

-- Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON citizen_affiliation.* TO 'djangouser'@'localhost';

-- Apply the privilege changes
FLUSH PRIVILEGES;

-- Display success message
SELECT 'Database and user created successfully!' AS status;

-- Show databases to verify
SHOW DATABASES LIKE 'citizen_affiliation';
