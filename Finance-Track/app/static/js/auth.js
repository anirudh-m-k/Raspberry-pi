/**
 * Authentication pages logic - Login, Register, Forgot Password
 */

// Password strength checker
function checkPasswordStrength(password) {
    let score = 0;
    let feedback = [];

    if (password.length >= 8) score++;
    else feedback.push('At least 8 characters');

    if (/[A-Z]/.test(password)) score++;
    else feedback.push('One uppercase letter');

    if (/[a-z]/.test(password)) score++;
    else feedback.push('One lowercase letter');

    if (/\d/.test(password)) score++;
    else feedback.push('One number');

    if (/[^A-Za-z0-9]/.test(password)) score++;

    return { score, feedback };
}

function updateStrengthMeter(password) {
    const meter = document.getElementById('strength-meter');
    const text = document.getElementById('strength-text');
    if (!meter || !text) return;

    const { score, feedback } = checkPasswordStrength(password);
    const levels = ['Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'];
    const colors = ['bg-danger', 'bg-orange-500', 'bg-warning', 'bg-blue-500', 'bg-success'];

    meter.className = `h-2 rounded-full transition-all duration-300 ${colors[score]} w-${(score + 1) * 20}`;
    text.textContent = password ? levels[score] : '';
    text.className = `text-xs mt-1 ${score >= 3 ? 'text-success' : score >= 2 ? 'text-warning' : 'text-danger'}`;
}

// Register form handler
async function handleRegister(e) {
    e.preventDefault();
    const form = e.target;
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn.textContent;

    btn.disabled = true;
    btn.textContent = 'Creating account...';

    try {
        const data = {
            name: form.name.value.trim(),
            email: form.email.value.trim(),
            password: form.password.value,
            confirm_password: form.confirm_password.value,
        };

        const result = await api.post('/auth/register', data);

        // Store token and user data
        api.setToken(result.data.token);
        api.setUser(result.data.user);

        showFlash('Registration successful!', 'success');
        setTimeout(() => window.location.href = '/dashboard', 500);
    } catch (error) {
        const message = error.error?.message || 'Registration failed';
        showFlash(message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// Login form handler
async function handleLogin(e) {
    e.preventDefault();
    const form = e.target;
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn.textContent;

    btn.disabled = true;
    btn.textContent = 'Signing in...';

    try {
        const data = {
            email: form.email.value.trim(),
            password: form.password.value,
        };

        const result = await api.post('/auth/login', data);

        api.setToken(result.data.token);
        api.setUser(result.data.user);

        showFlash('Login successful!', 'success');
        // Redirect admin to admin panel, regular users to dashboard
        const redirectUrl = result.data.user.role === 'admin' ? '/admin' : '/dashboard';
        setTimeout(() => window.location.href = redirectUrl, 500);
    } catch (error) {
        const message = error.error?.message || 'Login failed';
        showFlash(message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// Forgot password handler
async function handleForgotPassword(e) {
    e.preventDefault();
    const form = e.target;
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn.textContent;

    btn.disabled = true;
    btn.textContent = 'Sending...';

    try {
        const email = form.email.value.trim();
        await api.post('/auth/forgot-password', { email });

        showFlash('If the email exists, a password reset link has been sent', 'success');
        setTimeout(() => window.location.href = '/login', 2000);
    } catch (error) {
        const message = error.error?.message || 'Request failed';
        showFlash(message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}


