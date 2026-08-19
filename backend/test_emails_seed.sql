CREATE DATABASE IF NOT EXISTS hr_background_verification_db;
USE hr_background_verification_db;

CREATE TABLE IF NOT EXISTS emails (
  id INT PRIMARY KEY AUTO_INCREMENT,
  sender VARCHAR(255) NOT NULL,
  subject VARCHAR(500) NOT NULL,
  body TEXT NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'new',
  processing_status VARCHAR(20) NOT NULL DEFAULT 'new',
  received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS verification_decisions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  email_id INT NOT NULL,
  decision VARCHAR(50) NOT NULL,
  note TEXT NULL,
  decided_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_verification_decisions_email
    FOREIGN KEY (email_id) REFERENCES emails(id)
);

INSERT INTO emails (sender, subject, body)
SELECT
  'verification.vendor@example.com',
  'TEST PASS - Background verification request for Aarav Sharma',
  'Hello HR Team,\n\nPlease verify the employment details below.\n\nEmployee ID: EMP-1001\nEmployee Name: Aarav Sharma\nDate of Joining: 2021-04-12\nLast Working Day: 2025-06-30\n\nRegards,\nVerification Team'
WHERE NOT EXISTS (
  SELECT 1 FROM emails WHERE subject = 'TEST PASS - Background verification request for Aarav Sharma'
);

INSERT INTO emails (sender, subject, body)
SELECT
  'checks@example.com',
  'TEST FAIL - One day mismatch for Maya Iyer',
  'Dear HR,\n\nKindly confirm these submitted details.\n\nEmployee ID: EMP-1002\nEmployee Name: Maya Iyer\nDate of Joining: 20/01/2020\nLast Working Day: 16/12/2024\n\nThanks'
WHERE NOT EXISTS (
  SELECT 1 FROM emails WHERE subject = 'TEST FAIL - One day mismatch for Maya Iyer'
);

INSERT INTO emails (sender, subject, body)
SELECT
  'screening.partner@example.com',
  'TEST FLAG - Unknown employee verification',
  'Hello,\n\nPlease verify this candidate''s employment information.\n\nEmployee ID: EMP-9999\nEmployee Name: Rohan Mehta\nDate of Joining: 2022-03-01\nLast Working Day: 2025-01-31\n\nRegards,\nScreening Partner'
WHERE NOT EXISTS (
  SELECT 1 FROM emails WHERE subject = 'TEST FLAG - Unknown employee verification'
);
