-- =============================================================================
-- Database Initialization Script for Event-Driven Transactional Email Service
-- =============================================================================

-- 1. Notification Templates Table
CREATE TABLE IF NOT EXISTS notification_templates (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    subject_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 2. User Notification Preferences Table
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id VARCHAR(64) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    email_opt_out BOOLEAN DEFAULT FALSE NOT NULL,
    preferred_language VARCHAR(10) DEFAULT 'en' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create index on user email for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_preferences_email ON user_preferences(email);

-- =============================================================================
-- Seed Initial Sample Email Templates (At least 3 required)
-- =============================================================================

INSERT INTO notification_templates (id, name, subject_template, body_template, language)
VALUES 
    (
        'order-confirmation',
        'Order Confirmation',
        'Order Confirmation - {{ order_id }}',
        'Hello {{ customer_name }},\n\nThank you for your purchase! Your order #{{ order_id }} for {{ product_name }} has been confirmed.\nTotal amount: ${{ total_amount }}.\n\nBest regards,\nThe Store Team',
        'en'
    ),
    (
        'password-reset',
        'Password Reset Request',
        'Password Reset Request for {{ user_name }}',
        'Hello {{ user_name }},\n\nWe received a request to reset your password. Click the link below to set a new password:\n{{ reset_link }}\n\nNote: This link will expire in {{ expiry_minutes }} minutes. If you did not request this, please ignore this email.\n\nSecurity Team',
        'en'
    ),
    (
        'account-alert',
        'Security Account Alert',
        'Security Alert: New Sign-in from {{ device }}',
        'Dear {{ user_name }},\n\nWe noticed a new sign-in to your account from {{ device }} in {{ location }} on {{ login_time }}.\nIf this was you, no action is needed.\nIf this was not you, please secure your account immediately.\n\nSupport Team',
        'en'
    )
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- Seed Initial Sample User Notification Preferences (At least 5 required)
-- =============================================================================

INSERT INTO user_preferences (user_id, email, email_opt_out, preferred_language)
VALUES
    ('usr-001', 'alice@example.com', FALSE, 'en'),
    ('usr-002', 'bob.optout@example.com', TRUE, 'en'),
    ('usr-003', 'carlos@example.es', FALSE, 'es'),
    ('usr-004', 'diana@example.fr', FALSE, 'fr'),
    ('usr-005', 'evan@example.com', FALSE, 'en')
ON CONFLICT (user_id) DO NOTHING;
