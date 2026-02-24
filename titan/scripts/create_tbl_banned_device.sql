-- 기기 차단 테이블 (접속금지 기능)
-- 2026-02-11
CREATE TABLE IF NOT EXISTS `tbl_banned_device` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NULL COMMENT '차단 시점 유저 ID',
    `email` VARCHAR(100) NULL COMMENT '차단 시점 이메일',
    `device_uuid` VARCHAR(200) NULL COMMENT '기기 UUID (앱 재설치해도 동일한 기기 식별)',
    `device_ip` VARCHAR(200) NULL COMMENT '차단 시 IP',
    `device_type` VARCHAR(50) NULL COMMENT '기기 타입',
    `device_os` VARCHAR(200) NULL COMMENT 'OS 정보',
    `session_key` VARCHAR(200) NULL COMMENT '차단한 세션키',
    `reason` VARCHAR(500) NULL COMMENT '차단 사유',
    `ban_type` VARCHAR(20) NOT NULL DEFAULT 'session' COMMENT 'session=세션만, device=기기+세션, ip=IP+세션',
    `is_active` TINYINT NOT NULL DEFAULT 1 COMMENT '1=활성, 0=해제',
    `banned_by` VARCHAR(100) NULL COMMENT '차단 처리한 관리자',
    `regist_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `modify_date` DATETIME NULL,
    INDEX `idx_device_uuid` (`device_uuid`),
    INDEX `idx_device_ip` (`device_ip`),
    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_email` (`email`),
    INDEX `idx_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='기기/IP 접속 차단 테이블';
