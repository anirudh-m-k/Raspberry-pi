/**
 * API Client - Fetch wrapper with JWT auth headers and error handling
 */
const API_BASE = '/api/v1';

class ApiClient {
    constructor() {
        this.baseUrl = API_BASE;
    }

    getToken() {
        return localStorage.getItem('token');
    }

    setToken(token) {
        localStorage.setItem('token', token);
    }

    removeToken() {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    }

    clearToken() {
        this.removeToken();
    }

    getUser() {
        const user = localStorage.getItem('user');
        return user ? JSON.parse(user) : null;
    }

    setUser(user) {
        localStorage.setItem('user', JSON.stringify(user));
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const token = this.getToken();

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers,
            });

            if (response.status === 401) {
                this.removeToken();
                if (!window.location.pathname.match(/^\/(login|register|forgot-password|)$/)) {
                    window.location.href = '/login';
                }
                throw new Error('Unauthorized');
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                if (!response.ok) {
                    throw { status: response.status, ...data };
                }
                return data;
            }

            if (!response.ok) {
                throw { status: response.status, error: { message: 'Request failed' } };
            }

            return response;
        } catch (error) {
            if (error.status) {
                throw error;
            }
            throw { status: 0, error: { message: 'Network error. Please check your connection.' } };
        }
    }

    get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(url, { method: 'GET' });
    }

    post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    delete(endpoint, data = null) {
        const options = { method: 'DELETE' };
        if (data) {
            options.body = JSON.stringify(data);
        }
        return this.request(endpoint, options);
    }

    get token() {
        return this.getToken();
    }

    async upload(endpoint, formData, method = 'POST', options = {}) {
        const token = this.getToken();
        const { onProgress, timeout = 180000 } = options;

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open(method, `${this.baseUrl}${endpoint}`);
            xhr.timeout = timeout;

            if (token) {
                xhr.setRequestHeader('Authorization', `Bearer ${token}`);
            }

            if (onProgress && xhr.upload) {
                xhr.upload.addEventListener('progress', (e) => {
                    if (e.lengthComputable) {
                        onProgress(Math.round((e.loaded / e.total) * 100));
                    }
                });
            }

            xhr.onload = () => {
                if (xhr.status === 401) {
                    this.removeToken();
                    if (!window.location.pathname.match(/^\/(login|register|forgot-password|)$/)) {
                        window.location.href = '/login';
                    }
                    reject(new Error('Unauthorized'));
                    return;
                }

                let data = {};
                try {
                    data = JSON.parse(xhr.responseText);
                } catch (err) {
                    data = {};
                }

                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(data);
                } else {
                    reject({ status: xhr.status, ...data });
                }
            };

            xhr.onerror = () => reject({ status: 0, error: { message: 'Network error. Please check your connection.' } });
            xhr.ontimeout = () => reject({ status: 0, error: { message: 'Upload timed out. Please try again.' } });

            xhr.send(formData);
        });
    }

    async downloadFile(endpoint) {
        const token = this.getToken();
        const headers = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'GET',
            headers
        });

        if (response.status === 401) {
            this.removeToken();
            if (!window.location.pathname.match(/^\/(login|register|forgot-password|)$/)) {
                window.location.href = '/login';
            }
            throw new Error('Unauthorized');
        }

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data?.error?.message || 'Download failed');
        }

        const blob = await response.blob();
        let filename = null;
        const disposition = response.headers.get('content-disposition');
        if (disposition) {
            const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
            if (match && match[1]) {
                filename = decodeURIComponent(match[1]);
            }
        }

        return { blob, filename };
    }
}

// Global API client instance
const api = new ApiClient();
