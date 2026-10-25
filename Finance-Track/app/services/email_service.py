import random
import string
from flask_mail import Message
from flask import current_app
from datetime import datetime, timedelta
from app.extensions import mail


def send_email(to, subject, body, html=None):
    """Send an email."""
    try:
        msg = Message(
            subject=subject,
            recipients=[to],
            body=body,
            html=html,
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {e}")
        return False


def generate_otp():
    """Generate a 6-digit OTP."""
    return ''.join(random.choices(string.digits, k=6))


def send_password_reset_otp(email, otp):
    """Send password reset OTP email."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #4263eb;">Finance-Track Password Reset</h2>
        <p>You requested to reset your password. Your OTP is:</p>
        <div style="font-size: 32px; font-weight: bold; color: #4263eb; letter-spacing: 8px; text-align: center; padding: 20px; background: #f0f4ff; border-radius: 8px; margin: 20px 0;">{otp}</div>
        <p style="color: #666;">This OTP is valid for 10 minutes.</p>
        <p style="color: #999; font-size: 12px;">If you didn't request this, please ignore this email.</p>
    </div>
    """
    return send_email(
        to=email,
        subject='Finance-Track - Password Reset OTP',
        body=f'Your password reset OTP is: {otp}. Valid for 10 minutes.',
        html=html
    )


def send_welcome_email(email, name):
    """Send welcome email to newly registered user."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #4263eb;">Welcome to Finance-Track, {name}!</h2>
        <p>Your account has been created successfully. You can now start tracking your finances.</p>
        <div style="background: #f0f4ff; border-radius: 8px; padding: 20px; margin: 20px 0;">
            <p style="margin: 0 0 10px 0;"><strong>Here's what you can do:</strong></p>
            <ul style="margin: 0; padding-left: 20px;">
                <li>Track your expenses and income</li>
                <li>Set budgets and savings goals</li>
                <li>Manage recurring transactions</li>
                <li>View reports and insights</li>
            </ul>
        </div>
        <p style="color: #666;">If you have any questions, feel free to reach out to us.</p>
        <p style="color: #999; font-size: 12px;">This is an automated email. Please do not reply.</p>
    </div>
    """
    return send_email(
        to=email,
        subject='Welcome to Finance-Track!',
        body=f'Welcome to Finance-Track, {name}! Your account has been created successfully.',
        html=html
    )


def send_password_changed_email(email, name):
    """Send notification when password is changed."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #dc2626;">Finance-Track - Password Changed</h2>
        <p>Hello {name},</p>
        <p>Your password has been changed successfully.</p>
        <div style="background: #fef2f2; border-radius: 8px; padding: 20px; margin: 20px 0;">
            <p style="margin: 0; color: #dc2626; font-weight: bold;">If you didn't change your password, please secure your account immediately.</p>
        </div>
        <p style="color: #666;">If you need any help, contact our support team.</p>
        <p style="color: #999; font-size: 12px;">This is an automated email. Please do not reply.</p>
    </div>
    """
    return send_email(
        to=email,
        subject='Finance-Track - Password Changed',
        body=f'Hello {name}, your password has been changed. If you did not do this, please secure your account immediately.',
        html=html
    )


def send_account_deletion_otp(email, otp):
    """Send account deletion OTP email."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #dc2626;">Finance-Track - Account Deletion Request</h2>
        <p>You have requested to permanently delete your Finance-Track account. Your confirmation OTP is:</p>
        <div style="font-size: 32px; font-weight: bold; color: #dc2626; letter-spacing: 8px; text-align: center; padding: 20px; background: #fef2f2; border-radius: 8px; margin: 20px 0;">{otp}</div>
        <p style="color: #666;">This OTP is valid for 10 minutes.</p>
        <p style="color: #dc2626; font-weight: bold; font-size: 14px;">Warning: This action is permanent and cannot be undone. All your data will be deleted.</p>
        <p style="color: #999; font-size: 12px;">If you didn't request this, please ignore this email and secure your account.</p>
    </div>
    """
    return send_email(
        to=email,
        subject='Finance-Track - Account Deletion OTP',
        body=f'Your account deletion OTP is: {otp}. Valid for 10 minutes. WARNING: This is permanent.',
        html=html
    )
