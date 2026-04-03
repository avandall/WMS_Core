// WMS Dashboard JavaScript
// Version: 2026-01-28 - Customer Sales Report Feature
let API_BASE = 'http://localhost:8000';

// Auth state
let accessToken = localStorage.getItem('accessToken') || '';
let refreshToken = localStorage.getItem('refreshToken') || '';
let currentUser = null;
let realtimeHandle = null;
let selectedDocumentId = null;
let documentAutoRefreshHandle = null;

// Global state
let products = [];
let warehouses = [];
let documents = [];
let inventory = [];
let customers = [];

// Request management system to handle rapid switching
const RequestManager = {
    // Store active requests per endpoint
    activeRequests: new Map(),
    // Store abort controllers per endpoint
    abortControllers: new Map(),
    // Debounce timers
    debounceTimers: new Map(),
    
    /**
     * Cancel previous request for an endpoint and create new controller
     */
    getController(endpoint) {
        // Cancel existing request for this endpoint
        if (this.abortControllers.has(endpoint)) {
            this.abortControllers.get(endpoint).abort();
        }
        // Create new controller
        const controller = new AbortController();
        this.abortControllers.set(endpoint, controller);
        return controller;
    },
    
    /**
     * Debounce requests to prevent thundering herd
     */
    debounce(endpoint, fn, delay = 300) {
        // Clear existing timer
        if (this.debounceTimers.has(endpoint)) {
            clearTimeout(this.debounceTimers.get(endpoint));
        }
        // Set new timer
        const timer = setTimeout(() => {
            fn();
            this.debounceTimers.delete(endpoint);
        }, delay);
        this.debounceTimers.set(endpoint, timer);
    },
    
    /**
     * Track active request
     */
    trackRequest(endpoint, promise) {
        this.activeRequests.set(endpoint, promise);
        return promise.finally(() => {
            this.activeRequests.delete(endpoint);
        });
    },
    
    /**
     * Check if request is cancelled
     */
    isCancelled(endpoint) {
        const controller = this.abortControllers.get(endpoint);
        return controller && controller.signal.aborted;
    }
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    updateTime();
    setInterval(updateTime, 1000);
    setupEventListeners();
    
    // Setup edit form listeners (moved from separate DOMContentLoaded)
    const editProductForm = document.getElementById('edit-product-form');
    const editWarehouseForm = document.getElementById('edit-warehouse-form');
    
    if (editProductForm) {
        editProductForm.addEventListener('submit', handleEditProduct);
    }
    
    if (editWarehouseForm) {
        editWarehouseForm.addEventListener('submit', handleEditWarehouse);
    }
    
    // Add global click event listener to debug UI locking issues
    document.addEventListener('click', function(event) {
        // Log clicks for debugging
        if (event.target.tagName === 'BUTTON') {
            console.log('Button clicked:', event.target.textContent, event.target.disabled);
        }
    }, true); // Use capture phase
    
    // Add event listener for modal closed events
    document.addEventListener('modalClosed', function(event) {
        console.log('Modal closed event received:', event.detail.modalId);
        // Additional cleanup if needed
        document.body.style.cursor = '';
        document.body.style.pointerEvents = '';
    });
    
    updateAuthUI();
    const savedApiBase = localStorage.getItem('API_BASE');
    if (savedApiBase) {
        API_BASE = savedApiBase;
        const apiInput = document.getElementById('api-base-input');
        if (apiInput) apiInput.value = API_BASE;
    }
    if (accessToken) {
        fetchCurrentUser().finally(loadDashboardData);
    } else {
        loadDashboardData();
    }

    // Auto-refresh settings: keep on by default unless explicitly disabled
    const realtimeToggle = document.getElementById('realtime-toggle');
    const savedRealtime = localStorage.getItem('realtime_updates');
    const realtimeEnabled = savedRealtime === null ? true : savedRealtime === 'true';
    if (realtimeToggle) {
        realtimeToggle.checked = realtimeEnabled;
    }
    if (realtimeEnabled) {
        toggleRealtime(true);
    }
});

// Update current time
function updateTime() {
    const now = new Date();
    document.getElementById('current-time').textContent =
        now.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
}

// Setup event listeners
function setupEventListeners() {
    // Navigation - remove conflicting listeners, use inline onclick instead
    // document.querySelectorAll('.nav-btn').forEach(btn => {
    //     btn.addEventListener('click', function() {
    //         showSection(this.textContent.toLowerCase());
    //     });
    // });

    // Forms
    document.getElementById('product-form').addEventListener('submit', handleCreateProduct);
    document.getElementById('warehouse-form').addEventListener('submit', handleCreateWarehouse);
    document.getElementById('document-form').addEventListener('submit', handleCreateDocument);

    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    const userForm = document.getElementById('user-form');
    if (userForm) {
        userForm.addEventListener('submit', handleCreateUser);
    }

    const changePasswordForm = document.getElementById('change-password-form');
    if (changePasswordForm) {
        changePasswordForm.addEventListener('submit', handleChangePassword);
    }

    const customerForm = document.getElementById('customer-form');
    if (customerForm) {
        customerForm.addEventListener('submit', handleCreateCustomer);
    }

    const editCustomerForm = document.getElementById('edit-customer-form');
    if (editCustomerForm) {
        editCustomerForm.addEventListener('submit', handleUpdateCustomer);
    }

    // AI chat
    const aiMessage = document.getElementById('ai-message');
    if (aiMessage) {
        aiMessage.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                sendAiMessage();
            }
        });
    }
}

// Navigation
function showSection(sectionName) {
    // Update navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    if (event && event.target) {
        event.target.classList.add('active');
    } else {
        const btn = Array.from(document.querySelectorAll('.nav-btn')).find(b => b.textContent.toLowerCase() === sectionName);
        if (btn) btn.classList.add('active');
    }

    // Show section
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(`${sectionName}-section`).classList.add('active');

    // Load section data
    switch(sectionName) {
        case 'products':
            loadProducts();
            break;
        case 'warehouses':
            loadWarehouses();
            break;
        case 'inventory':
            loadInventory();
            break;
        case 'documents':
            loadDocuments();
            break;
        case 'customers':
            loadCustomers();
            break;
        case 'users':
            loadUsers();
            break;
        case 'settings':
            // no-op; settings uses toggles/inputs
            break;
        case 'ai':
            // focus input for quick chat
            setTimeout(() => {
                const el = document.getElementById('ai-message');
                if (el) el.focus();
            }, 0);
            break;
    }
}

// API helper functions
async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
    }

    // Get abort controller for this endpoint
    const controller = RequestManager.getController(endpoint);
    
    // Add request timeout (30 seconds)
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    try {
        const fetchOptions = {
            ...options,
            headers,
            signal: controller.signal,
        };

        const response = await fetch(`${API_BASE}${endpoint}`, fetchOptions);

        clearTimeout(timeoutId);

        if (response.status === 401 && refreshToken) {
            // try refresh once
            const refreshed = await refreshAccessToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${accessToken}`;
                const retryController = new AbortController();
                const retryTimeoutId = setTimeout(() => retryController.abort(), 30000);
                
                const retry = await fetch(`${API_BASE}${endpoint}`, {
                    ...options,
                    headers,
                    signal: retryController.signal,
                });
                
                clearTimeout(retryTimeoutId);
                
                if (!retry.ok) {
                    const errorData = await retry.json().catch(() => ({}));
                    const errorMsg = errorData.detail || `HTTP ${retry.status}: ${retry.statusText}`;
                    const error = new Error(errorMsg);
                    error.status = retry.status;
                    error.detail = errorData.detail;
                    throw error;
                }
                return await retry.json();
            }
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            
            // Handle rate limit errors specially
            if (response.status === 429) {
                console.warn('Rate limit exceeded - slowing down requests');
                const rateLimitError = new Error('Too many requests. Please slow down your navigation.');
                rateLimitError.status = 429;
                rateLimitError.isRateLimit = true;
                throw rateLimitError;
            }
            
            const errorMsg = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
            const error = new Error(errorMsg);
            error.status = response.status;
            error.detail = errorData.detail;
            throw error;
        }

        // some endpoints may return no body
        const text = await response.text();
        return text ? JSON.parse(text) : {};
    } catch (error) {
        clearTimeout(timeoutId);
        
        // Handle aborted requests (user switched sections)
        if (error.name === 'AbortError') {
            console.log(`Request to ${endpoint} was cancelled (user navigated away)`);
            return null; // Return null instead of throwing
        }
        
        // Handle network errors with better error messages
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError') || error.isNetworkError) {
            console.error('Network error - is the server running?', error);
            const netError = new Error('Server connection failed. Please check if the server is running.');
            netError.isNetworkError = true;
            throw netError;
        }
        
        // Handle CORS errors specifically
        if (error.message.includes('CORS') || error.message.includes('Cross-Origin')) {
            console.error('CORS error - server configuration issue', error);
            const corsError = new Error('Server configuration error. Please contact administrator.');
            corsError.isCorsError = true;
            throw corsError;
        }
        
        console.error('API request failed:', error);
        throw error;
    }
}

async function refreshAccessToken() {
    if (!refreshToken) return false;
    try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        if (!res.ok) {
            logout();
            return false;
        }
        const data = await res.json();
        accessToken = data.access_token;
        refreshToken = data.refresh_token;
        localStorage.setItem('accessToken', accessToken);
        localStorage.setItem('refreshToken', refreshToken);
        updateAuthUI();
        return true;
    } catch (e) {
        logout();
        return false;
    }
}

async function handleLogin(event) {
    event.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    try {
        const res = await fetch('http://localhost:8000/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        if (!res.ok) throw new Error('Login failed');
        const data = await res.json();
        accessToken = data.access_token;
        refreshToken = data.refresh_token;
        localStorage.setItem('accessToken', accessToken);
        localStorage.setItem('refreshToken', refreshToken);
        currentUser = data.user;
        updateAuthUI();
        closeModal('login-modal');
        loadDashboardData();
        loadUsers();
        showSuccess('Logged in');
    } catch (e) {
        showError(e.message);
    }
}

async function fetchCurrentUser() {
    try {
        const res = await apiRequest('/api/users/me');
        currentUser = res;
        updateAuthUI();
    } catch (e) {
        console.warn('Failed to fetch current user', e);
    }
}

function updateAuthUI() {
    const emailEl = document.getElementById('user-email');
    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const changePasswordBtn = document.getElementById('change-password-btn');
    if (!emailEl || !loginBtn || !logoutBtn) return;
    if (currentUser || accessToken) {
        emailEl.textContent = currentUser?.email || 'Authenticated';
        loginBtn.style.display = 'none';
        logoutBtn.style.display = 'inline-flex';
        if (changePasswordBtn) changePasswordBtn.style.display = 'inline-flex';
    } else {
        emailEl.textContent = 'Guest';
        loginBtn.style.display = 'inline-flex';
        logoutBtn.style.display = 'none';
        if (changePasswordBtn) changePasswordBtn.style.display = 'none';
    }
}

function openLoginModal() {
    openModal('login-modal');
}

function logout() {
    accessToken = '';
    refreshToken = '';
    currentUser = null;
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    updateAuthUI();
    openLoginModal();
}

function updateApiBase(value) {
    API_BASE = value.trim();
    localStorage.setItem('API_BASE', API_BASE);
    showSuccess('API base updated');
}

// Load dashboard overview data
async function loadDashboardData() {
    if (!accessToken) {
        openLoginModal();
        return;
    }
    try {
        // Load all data in parallel
        const [productsRes, warehousesRes, inventoryRes, documentsRes] = await Promise.allSettled([
            apiRequest('/api/products'),
            apiRequest('/api/warehouses'),
            apiRequest('/api/inventory'),
            apiRequest('/api/documents')
        ]);

        // Update stats
        if (productsRes.status === 'fulfilled') {
            products = productsRes.value || [];
            document.getElementById('total-products').textContent = products.length;
        }

        if (warehousesRes.status === 'fulfilled') {
            warehouses = warehousesRes.value || [];
            document.getElementById('total-warehouses').textContent = warehouses.length;
        }

        if (inventoryRes.status === 'fulfilled') {
            inventory = inventoryRes.value || [];
            const totalItems = inventory.reduce((sum, item) => sum + item.quantity, 0);
            document.getElementById('total-inventory').textContent = totalItems;
        }

        if (documentsRes.status === 'fulfilled') {
            documents = documentsRes.value || [];
            const today = new Date().toISOString().split('T')[0];
            const todayDocs = documents.filter(doc => doc.date && doc.date.startsWith(today));
            document.getElementById('today-documents').textContent = todayDocs.length;
        }

        // Load recent activity
        loadRecentActivity();
        
        // Update connection status to show server is connected
        updateConnectionStatus(true);

    } catch (error) {
        console.error('Failed to load dashboard data:', error);
        updateConnectionStatus(false);
    }
}

// Load recent activity
function loadRecentActivity() {
    const activityList = document.getElementById('recent-activity-list');
    const recentItems = [];

    // Get recent documents
    const recentDocs = documents
        .sort((a, b) => new Date(b.date) - new Date(a.date))
        .slice(0, 5);

    recentDocs.forEach(doc => {
        recentItems.push({
            title: `${doc.doc_type} Document #${doc.document_id}`,
            description: `Created ${new Date(doc.date).toLocaleString()}`,
            type: 'document'
        });
    });

    if (recentItems.length === 0) {
        activityList.innerHTML = '<p>No recent activity</p>';
        return;
    }

    activityList.innerHTML = recentItems.map(item => `
        <div class="activity-item">
            <h4>${item.title}</h4>
            <p>${item.description}</p>
        </div>
    `).join('');
}

// Load products
async function loadProducts() {
    const endpoint = '/api/products';
    RequestManager.debounce(endpoint, async () => {
        try {
            const productsList = document.getElementById('products-list');
            if (RequestManager.isCancelled(endpoint)) return;
            
            productsList.innerHTML = '<p>Loading products...</p>';

            if (products.length === 0) {
                try {
                    const response = await apiRequest(endpoint);
                    // Check if request was cancelled (response will be null)
                    if (response === null || RequestManager.isCancelled(endpoint)) {
                        console.log('Products request was cancelled');
                        return;
                    }
                    products = response || [];
                } catch (error) {
                    if (error.isNetworkError) {
                        productsList.innerHTML = `<p style="color: red;">❌ ${error.message}</p>`;
                        return;
                    }
                    if (error.isRateLimit) {
                        productsList.innerHTML = `<p style="color: orange;">⚠️ ${error.message}</p>`;
                        return;
                    }
                    throw error;
                }
            }

            if (RequestManager.isCancelled(endpoint)) return;

            if (products.length === 0) {
                productsList.innerHTML = '<p>No products found. Create your first product!</p>';
                return;
            }

            const tableHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Price</th>
                            <th>Description</th>
                            <th>Actions</th>
                        </tr>
                        <tr class="filter-row">
                            <th><input type="text" class="filter-input" data-column="product_id" placeholder="Filter ID" onkeyup="applyProductFilters()"></th>
                            <th><input type="text" class="filter-input" data-column="name" placeholder="Filter Name" onkeyup="applyProductFilters()"></th>
                            <th><input type="text" class="filter-input" data-column="price" placeholder="Filter Price" onkeyup="applyProductFilters()"></th>
                            <th><input type="text" class="filter-input" data-column="description" placeholder="Filter Description" onkeyup="applyProductFilters()"></th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${products.map(product => `
                            <tr>
                                <td>${product.product_id}</td>
                                <td>${product.name}</td>
                                <td>$${product.price.toFixed(2)}</td>
                                <td>${product.description || '-'}</td>
                                <td>
                                    <button class="btn-secondary" onclick="editProduct(${product.product_id})">Edit</button>
                                    <button class="btn-secondary" onclick="deleteProduct(${product.product_id})" style="background: #dc3545;">Delete</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;

            if (RequestManager.isCancelled(endpoint)) return;
            productsList.innerHTML = tableHTML;
        } catch (error) {
            if (!error.message.includes('Request cancelled')) {
                const productsList = document.getElementById('products-list');
                if (productsList) {
                    productsList.innerHTML = '<p class="error">Failed to load products: ' + (error.message || 'Unknown error') + '</p>';
                }
            }
        }
    }, 200);
}

function filterProducts() {
    const term = document.getElementById('product-search').value.toLowerCase();
    const filtered = products.filter(p =>
        p.name.toLowerCase().includes(term) ||
        String(p.product_id).includes(term) ||
        (p.description || '').toLowerCase().includes(term)
    );
    const productsList = document.getElementById('products-list');
    productsList.innerHTML = filtered.length === 0 ? '<p>No matching products</p>' : `
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Price</th>
                    <th>Description</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${filtered.map(product => `
                    <tr>
                        <td>${product.product_id}</td>
                        <td>${product.name}</td>
                        <td>$${product.price.toFixed(2)}</td>
                        <td>${product.description || '-'}</td>
                        <td>
                            <button class="btn-secondary" onclick="editProduct(${product.product_id})">Edit</button>
                            <button class="btn-secondary" onclick="deleteProduct(${product.product_id})" style="background: #dc3545;">Delete</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Load warehouses
async function loadWarehouses() {
    const endpoint = '/api/warehouses';
    RequestManager.debounce(endpoint, async () => {
        try {
            const warehousesList = document.getElementById('warehouses-list');
            if (RequestManager.isCancelled(endpoint)) return;
            
            warehousesList.innerHTML = '<p>Loading warehouses...</p>';

            if (warehouses.length === 0) {
                try {
                    const response = await apiRequest(endpoint);
                    if (response === null || RequestManager.isCancelled(endpoint)) return;
                    warehouses = response || [];
                } catch (error) {
                    if (error.message && error.message.includes('Request cancelled')) return;
                    if (error.isNetworkError) {
                        warehousesList.innerHTML = `<p style="color: red;">❌ ${error.message}</p>`;
                        return;
                    }
                    throw error;
                }
            }

            if (RequestManager.isCancelled(endpoint)) return;

            if (warehouses.length === 0) {
                warehousesList.innerHTML = '<p>No warehouses found. Create your first warehouse!</p>';
                return;
            }

            const tableHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Actions</th>
                        </tr>
                        <tr class="filter-row">
                            <th><input type="text" class="filter-input" data-column="warehouse_id" placeholder="Filter ID" onkeyup="applyWarehouseFilters()"></th>
                            <th><input type="text" class="filter-input" data-column="name" placeholder="Filter Name" onkeyup="applyWarehouseFilters()"></th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${warehouses.map(warehouse => `
                            <tr>
                                <td>${warehouse.warehouse_id}</td>
                                <td>${warehouse.name || warehouse.location}</td>
                                <td>
                                    <button class="btn-secondary" onclick="viewWarehouseInventory(${warehouse.warehouse_id})">View Inventory</button>
                                    <button class="btn-secondary" onclick="editWarehouse(${warehouse.warehouse_id})">Edit</button>
                                    <button class="btn-danger" onclick="deleteWarehouse(${warehouse.warehouse_id})">Delete</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;

            if (RequestManager.isCancelled(endpoint)) return;
            warehousesList.innerHTML = tableHTML;
        } catch (error) {
            if (!error.message.includes('Request cancelled')) {
                const warehousesList = document.getElementById('warehouses-list');
                if (warehousesList) {
                    warehousesList.innerHTML = '<p class="error">Failed to load warehouses: ' + (error.message || 'Unknown error') + '</p>';
                }
            }
        }
    }, 200);
}

function filterWarehouses() {
    const term = document.getElementById('warehouse-search').value.toLowerCase();
    const filtered = warehouses.filter(w =>
        (w.name || w.location).toLowerCase().includes(term) || String(w.warehouse_id).includes(term)
    );
    const warehousesList = document.getElementById('warehouses-list');
    warehousesList.innerHTML = filtered.length === 0 ? '<p>No matching warehouses</p>' : `
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${filtered.map(warehouse => `
                    <tr>
                        <td>${warehouse.warehouse_id}</td>
                        <td>${warehouse.name || warehouse.location}</td>
                        <td>
                            <button class="btn-secondary" onclick="viewWarehouseInventory(${warehouse.warehouse_id})">View Inventory</button>
                            <button class="btn-secondary" onclick="editWarehouse(${warehouse.warehouse_id})">Edit</button>
                            <button class="btn-danger" onclick="deleteWarehouse(${warehouse.warehouse_id})">Delete</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function filterUsers() {
    const term = document.getElementById('users-search')?.value.toLowerCase() || '';
    const usersList = document.getElementById('users-list');
    if (!usersList) return;
    const rows = Array.from(usersList.querySelectorAll('tbody tr'));
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(term) ? '' : 'none';
    });
}

// Column-based filter functions
function applyProductFilters() {
    const table = document.querySelector('#products-list table');
    if (!table) return;
    const filters = {};
    table.querySelectorAll('.filter-row input').forEach(input => {
        filters[input.dataset.column] = input.value.toLowerCase();
    });
    table.querySelectorAll('tbody tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        let match = true;
        const columns = ['product_id', 'name', 'price', 'description'];
        columns.forEach((col, idx) => {
            if (filters[col] && !cells[idx]?.textContent.toLowerCase().includes(filters[col])) {
                match = false;
            }
        });
        row.style.display = match ? '' : 'none';
    });
}

function applyWarehouseFilters() {
    const table = document.querySelector('#warehouses-list table');
    if (!table) return;
    const filters = {};
    table.querySelectorAll('.filter-row input').forEach(input => {
        filters[input.dataset.column] = input.value.toLowerCase();
    });
    table.querySelectorAll('tbody tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        let match = true;
        const columns = ['warehouse_id', 'name'];
        columns.forEach((col, idx) => {
            if (filters[col] && !cells[idx]?.textContent.toLowerCase().includes(filters[col])) {
                match = false;
            }
        });
        row.style.display = match ? '' : 'none';
    });
}

function applyDocumentFilters() {
    const table = document.querySelector('#documents-list table');
    if (!table) return;
    const filters = {};
    table.querySelectorAll('.filter-row input').forEach(input => {
        filters[input.dataset.column] = input.value.toLowerCase();
    });
    table.querySelectorAll('tbody tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        let match = true;
        const columns = ['document_id', 'doc_type', 'status', 'created_by', 'date'];
        columns.forEach((col, idx) => {
            if (filters[col] && !cells[idx]?.textContent.toLowerCase().includes(filters[col])) {
                match = false;
            }
        });
        row.style.display = match ? '' : 'none';
    });
}

function applyCustomerFilters() {
    const table = document.querySelector('#customers-list table');
    if (!table) return;
    const filters = {};
    table.querySelectorAll('.filter-row input').forEach(input => {
        filters[input.dataset.column] = input.value.toLowerCase();
    });
    table.querySelectorAll('tbody tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        let match = true;
        // Check name, contact (email/phone), debt, purchases, total
        if (filters['name'] && !cells[0]?.textContent.toLowerCase().includes(filters['name'])) match = false;
        if (filters['contact'] && !cells[1]?.textContent.toLowerCase().includes(filters['contact'])) match = false;
        if (filters['debt'] && !cells[2]?.textContent.toLowerCase().includes(filters['debt'])) match = false;
        if (filters['purchases'] && !cells[3]?.textContent.toLowerCase().includes(filters['purchases'])) match = false;
        if (filters['total'] && !cells[4]?.textContent.toLowerCase().includes(filters['total'])) match = false;
        row.style.display = match ? '' : 'none';
    });
}

function applyInventoryFilters() {
    const table = document.querySelector('#inventory-list table');
    if (!table) return;
    const filters = {};
    table.querySelectorAll('.filter-row input').forEach(input => {
        filters[input.dataset.column] = input.value.toLowerCase();
    });
    table.querySelectorAll('tbody tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        let match = true;
        const columns = ['product', 'warehouse', 'quantity', 'price', 'value'];
        columns.forEach((col, idx) => {
            if (filters[col] && !cells[idx]?.textContent.toLowerCase().includes(filters[col])) {
                match = false;
            }
        });
        row.style.display = match ? '' : 'none';
    });
}

function applyUserFilters() {
    const table = document.querySelector('#users-list table');
    if (!table) return;
    const filters = {};
    table.querySelectorAll('.filter-row input').forEach(input => {
        filters[input.dataset.column] = input.value.toLowerCase();
    });
    table.querySelectorAll('tbody tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        let match = true;
        const columns = ['user_id', 'email', 'role', 'status'];
        columns.forEach((col, idx) => {
            if (filters[col] && !cells[idx]?.textContent.toLowerCase().includes(filters[col])) {
                match = false;
            }
        });
        row.style.display = match ? '' : 'none';
    });
}

// Load inventory
async function loadInventory() {
    const endpoint = '/api/inventory/by-warehouse';
    RequestManager.debounce(endpoint, async () => {
        try {
            const inventoryDiv = document.getElementById('inventory-list');
            if (RequestManager.isCancelled(endpoint)) return;

            inventoryDiv.innerHTML = '<p>Loading inventory data...</p>';

            // Always refresh the per-warehouse inventory for correctness
            const response = await apiRequest(endpoint);
            if (response === null || RequestManager.isCancelled(endpoint)) return;
            inventory = response || [];

            if (RequestManager.isCancelled(endpoint)) return;

            if (inventory.length === 0) {
                inventoryDiv.innerHTML = '<p>No inventory data available</p>';
                loadInventorySummary();
                return;
            }

            const tableHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>Product</th>
                            <th>Warehouse Name</th>
                            <th>Quantity</th>
                            <th>Unit Price</th>
                            <th>Total Value</th>
                        </tr>
                        <tr class="filter-row">
                            <th><input type="text" class="filter-input" data-column="product" placeholder="Filter Product" onkeyup="applyInventoryFilters()"></th>
                            <th><input type="text" class="filter-input" data-column="warehouse" placeholder="Filter Warehouse" onkeyup="applyInventoryFilters()"></th>
                            <th><input type="text" class="filter-input" data-column="quantity" placeholder="Filter Qty" onkeyup="applyInventoryFilters()"></th>
                            <th><input type="text" class="filter-input" data-column="price" placeholder="Filter Price" onkeyup="applyInventoryFilters()"></th>
                            <th><input type="text" class="filter-input" data-column="value" placeholder="Filter Value" onkeyup="applyInventoryFilters()"></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${inventory.map(item => {
                            const product = products.find(p => p.product_id === item.product_id);
                            const wh = warehouses.find(w => w.warehouse_id === item.warehouse_id);
                            const warehouseName = item.warehouse_name || wh?.name || wh?.location || `Warehouse ${item.warehouse_id}`;
                            const totalValue = (product?.price || 0) * item.quantity;
                            return `
                                <tr>
                                    <td>${product ? product.name : `Product ${item.product_id}`}</td>
                                    <td>${warehouseName}</td>
                                    <td>${item.quantity}</td>
                                    <td>$${((product?.price || 0).toFixed(2))}</td>
                                    <td>$${totalValue.toFixed(2)}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            `;

            if (RequestManager.isCancelled(endpoint)) return;
            inventoryDiv.innerHTML = tableHTML;
            loadInventorySummary();
        } catch (error) {
            if (!error.message.includes('Request cancelled')) {
                const inventoryDiv = document.getElementById('inventory-list');
                if (inventoryDiv) {
                    inventoryDiv.innerHTML = '<p class="error">Failed to load inventory: ' + (error.detail || error.message || 'Unknown error') + '</p>';
                }
            }
        }
    }, 200);
}

function loadInventorySummary() {
    try {
        const summaryDiv = document.getElementById('inventory-overview');

        // Group by warehouse
        const warehouseInventory = {};
        inventory.forEach(item => {
            if (!warehouseInventory[item.warehouse_id]) {
                warehouseInventory[item.warehouse_id] = [];
            }
            warehouseInventory[item.warehouse_id].push(item);
        });

        const inventoryHTML = Object.entries(warehouseInventory).map(([warehouseId, items]) => {
            const wh = warehouses.find(w => w.warehouse_id == warehouseId);
            const name = items[0]?.warehouse_name || wh?.name || wh?.location || `Warehouse ${warehouseId}`;

            const totalItems = items.reduce((sum, item) => sum + item.quantity, 0);
            const totalValue = items.reduce((sum, item) => {
                const product = products.find(p => p.product_id === item.product_id);
                return sum + (product ? product.price * item.quantity : 0);
            }, 0);

            return `
                <div class="inventory-item">
                    <h3>${name}</h3>
                    <div class="inventory-stats">
                        <div class="stat-item">
                            <span class="number">${items.length}</span>
                            <span class="label">Products</span>
                        </div>
                        <div class="stat-item">
                            <span class="number">${totalItems}</span>
                            <span class="label">Total Items</span>
                        </div>
                        <div class="stat-item">
                            <span class="number">$${totalValue.toFixed(2)}</span>
                            <span class="label">Total Value</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        summaryDiv.innerHTML = inventoryHTML || '<p>No inventory data</p>';
    } catch (error) {
        console.error('Failed to load inventory summary:', error);
    }
}

// Load documents
async function loadDocuments() {
    const endpoint = '/api/documents';
    RequestManager.debounce(endpoint, async () => {
        try {
            const documentsList = document.getElementById('documents-list');
            if (RequestManager.isCancelled(endpoint)) return;
            
            documentsList.innerHTML = '<p>Loading documents...</p>';

            if (documents.length === 0) {
                try {
                    const response = await apiRequest(endpoint);
                    // If response is null, request was cancelled
                    if (response === null || RequestManager.isCancelled(endpoint)) return;
                    documents = response || [];
                } catch (error) {
                    // Silently handle cancelled requests
                    if (error.message && error.message.includes('Request cancelled')) return;
                    // Show network errors to user
                    if (error.isNetworkError) {
                        documentsList.innerHTML = `<p style="color: red;">❌ ${error.message}</p>`;
                        return;
                    }
                    throw error;
                }
            }

        if (documents.length === 0) {
            documentsList.innerHTML = '<p>No documents found. Create your first document!</p>';
            return;
        }

        const tableHTML = `
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Created By</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                    <tr class="filter-row">
                        <th><input type="text" class="filter-input" data-column="document_id" placeholder="Filter ID" onkeyup="applyDocumentFilters()"></th>
                        <th><input type="text" class="filter-input" data-column="doc_type" placeholder="Filter Type" onkeyup="applyDocumentFilters()"></th>
                        <th><input type="text" class="filter-input" data-column="status" placeholder="Filter Status" onkeyup="applyDocumentFilters()"></th>
                        <th><input type="text" class="filter-input" data-column="created_by" placeholder="Filter User" onkeyup="applyDocumentFilters()"></th>
                        <th><input type="text" class="filter-input" data-column="date" placeholder="Filter Date" onkeyup="applyDocumentFilters()"></th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    ${documents.slice(0, 20).map(doc => `
                        <tr>
                            <td>${doc.document_id}</td>
                            <td>${doc.doc_type}</td>
                            <td><span style="padding:4px 8px;border-radius:4px;background:#${doc.status.toLowerCase() === 'draft' ? 'fff3cd' : doc.status.toLowerCase() === 'posted' ? 'cfe2ff' : 'd1e7dd'}">${doc.status}</span></td>
                            <td>${doc.created_by || '-'}</td>
                            <td>${new Date(doc.date).toLocaleDateString()}</td>
                            <td>
                                <button class="btn-secondary" onclick="viewDocument(${doc.document_id})" style="padding:4px 8px;font-size:0.9em">View</button>
                                ${doc.status.toLowerCase() === 'draft' ? `<button class="btn-primary" onclick="postDocument(${doc.document_id})" style="padding:4px 8px;font-size:0.9em">Approve & Post</button>` : ''}
                                ${doc.status.toLowerCase() === 'draft' ? `<button class="btn-secondary" onclick="deleteDocument(${doc.document_id})" style="padding:4px 8px;font-size:0.9em;background:#dc3545;">Delete</button>` : ''}
                                ${doc.status.toLowerCase() === 'posted' ? `<span style="color:#6c757d;font-size:0.9em">Posted</span>` : ''}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

            if (RequestManager.isCancelled(endpoint)) return;
            documentsList.innerHTML = tableHTML;
        } catch (error) {
            if (!error.message.includes('Request cancelled')) {
                const documentsList = document.getElementById('documents-list');
                if (documentsList) {
                    documentsList.innerHTML = '<p class="error">Failed to load documents: ' + (error.message || 'Unknown error') + '</p>';
                }
            }
        }
    }, 200);
}

// Load users (admin only)
async function loadUsers() {
    const endpoint = '/api/users';
    RequestManager.debounce(endpoint, async () => {
        try {
            const usersList = document.getElementById('users-list');
            if (RequestManager.isCancelled(endpoint)) return;
            
            usersList.innerHTML = '<p>Loading users...</p>';
            
            const response = await apiRequest(endpoint);
            if (response === null || RequestManager.isCancelled(endpoint)) return;
            
            if (!response || response.length === 0) {
                usersList.innerHTML = '<p>No users found.</p>';
                return;
            }
            
            // Create table manually to avoid onclick issues
            const table = document.createElement('table');
            
            // Create header
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            ['ID', 'Email', 'Role', 'Status', 'Actions'].forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);

            // Create filter row
            const filterRow = document.createElement('tr');
            filterRow.className = 'filter-row';
            const filterColumns = [
                { label: 'Filter ID', data: 'user_id' },
                { label: 'Filter Email', data: 'email' },
                { label: 'Filter Role', data: 'role' },
                { label: 'Filter Status', data: 'status' },
                { label: '', data: '' }
            ];
            filterColumns.forEach(col => {
                const th = document.createElement('th');
                if (col.data) {
                    const input = document.createElement('input');
                    input.type = 'text';
                    input.className = 'filter-input';
                    input.dataset.column = col.data;
                    input.placeholder = col.label;
                    input.onkeyup = () => applyUserFilters();
                    th.appendChild(input);
                }
                filterRow.appendChild(th);
            });
            thead.appendChild(filterRow);
            table.appendChild(thead);
            
            // Create body
            const tbody = document.createElement('tbody');
            response.forEach(u => {
                const row = document.createElement('tr');
                
                // ID
                const tdId = document.createElement('td');
                tdId.textContent = u.user_id;
                row.appendChild(tdId);
                
                // Email
                const tdEmail = document.createElement('td');
                tdEmail.textContent = u.email;
                row.appendChild(tdEmail);
                
                // Role
                const tdRole = document.createElement('td');
                tdRole.textContent = u.role;
                row.appendChild(tdRole);
                
                // Status
                const tdStatus = document.createElement('td');
                tdStatus.textContent = u.is_active ? 'Active' : 'Inactive';
                row.appendChild(tdStatus);
                
                // Actions
                const tdActions = document.createElement('td');
                
                // Manage button
                const manageBtn = document.createElement('button');
                manageBtn.className = 'btn-secondary';
                manageBtn.textContent = 'Manage';
                manageBtn.onclick = () => openManageUserModal(u.user_id);
                tdActions.appendChild(manageBtn);
                
                // Delete button
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn-danger';
                deleteBtn.textContent = 'Delete';
                deleteBtn.onclick = () => deleteUserConfirm(u.user_id, u.email);
                tdActions.appendChild(deleteBtn);
                
                row.appendChild(tdActions);
                tbody.appendChild(row);
            });
            table.appendChild(tbody);
            
            usersList.innerHTML = '';
            usersList.appendChild(table);
            
        } catch (error) {
            console.error('Failed to load users:', error);
            if (error.isNetworkError) {
                document.getElementById('users-list').innerHTML = `<p style="color: red;">❌ ${error.message}</p>`;
                return;
            }
            // Show the actual error message from the API
            const errorMsg = error.detail || error.message || 'Failed to load users. You may not have sufficient permissions.';
            document.getElementById('users-list').innerHTML = `<p class="error">${errorMsg}</p>`;
        }
    });
}

// Load customers
async function loadCustomers() {
    const endpoint = '/api/customers';
    RequestManager.debounce(endpoint, async () => {
        try {
            const customersList = document.getElementById('customers-list');
            if (customersList) customersList.innerHTML = '<p>Loading customers...</p>';
            if (RequestManager.isCancelled(endpoint)) return;

            let response;
            try {
                response = await apiRequest(endpoint);
                // If response is null, request was cancelled
                if (response === null || RequestManager.isCancelled(endpoint)) return;
                customers = response || [];
            } catch (error) {
                // Silently handle cancelled requests
                if (error.message && error.message.includes('Request cancelled')) return;
                // Show network errors to user
                if (error.isNetworkError && customersList) {
                    customersList.innerHTML = `<p style="color: red;">❌ ${error.message}</p>`;
                    return;
                }
                throw error;
            }

        populateCustomerSelect();

        if (!customersList) return;
        if (customers.length === 0) {
            customersList.innerHTML = '<p>No customers found.</p>';
            return;
        }

        const tableHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Contact</th>
                        <th>Debt</th>
                        <th>Purchases</th>
                        <th>Total Spent</th>
                        <th>Actions</th>
                    </tr>
                    <tr class="filter-row">
                        <th><input type="text" class="filter-input" data-column="name" placeholder="Filter Name" onkeyup="applyCustomerFilters()"></th>
                        <th><input type="text" class="filter-input" data-column="contact" placeholder="Filter Contact" onkeyup="applyCustomerFilters()"></th>
                        <th><input type="text" class="filter-input" data-column="debt" placeholder="Filter Debt" onkeyup="applyCustomerFilters()"></th>
                        <th><input type="text" class="filter-input" data-column="purchases" placeholder="Filter Count" onkeyup="applyCustomerFilters()"></th>
                        <th><input type="text" class="filter-input" data-column="total" placeholder="Filter Total" onkeyup="applyCustomerFilters()"></th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    ${customers.map(c => `
                        <tr>
                            <td>${c.name}</td>
                            <td>${c.email || ''}${c.phone ? `<br>${c.phone}` : ''}</td>
                            <td>$${(c.debt_balance || 0).toFixed(2)}</td>
                            <td>${c.purchase_count || 0}</td>
                            <td>$${(c.total_purchased || 0).toFixed(2)}</td>
                            <td>
                                <button class="btn-secondary" style="padding:4px 8px;font-size:0.9em" onclick="viewCustomer(${c.customer_id})">View</button>
                                <button class="btn-secondary" style="padding:4px 8px;font-size:0.9em;margin-left:4px" onclick="openEditCustomerModal(${c.customer_id})">Edit</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

            if (RequestManager.isCancelled(endpoint)) return;
            customersList.innerHTML = tableHTML;
        } catch (error) {
            if (!error.message.includes('Request cancelled')) {
                const customersList = document.getElementById('customers-list');
                if (customersList) {
                    customersList.innerHTML = '<p class="error">Failed to load customers: ' + (error.message || 'Unknown error') + '</p>';
                }
            }
        }
    }, 200);
}

// Form handlers
async function handleCreateProduct(event) {
    event.preventDefault();

    const submitButton = event.target.querySelector('button[type="submit"]');
    const formData = new FormData(event.target);
    const productData = {
        product_id: Date.now(), // Simple ID generation
        name: document.getElementById('product-name').value,
        description: document.getElementById('product-description').value
    };

    try {
        await apiRequestWithButton('/api/products', {
            method: 'POST',
            body: JSON.stringify(productData)
        }, submitButton);

        showSuccess('Product created successfully!');
        closeModalAndCleanup('product-modal');
        event.target.reset();
        products = []; // Reset cache
        loadProducts();
        loadDashboardData();
    } catch (error) {
        // Button state is automatically reset by apiRequestWithButton
        if (error.isNetworkError) {
            showError('Server connection failed. Please check your network connection.');
        } else if (error.isCorsError) {
            showError('Server configuration error. Please contact administrator.');
        } else {
            showError('Failed to create product: ' + (error.message || 'Unknown error'));
        }
    }
}

async function handleCreateWarehouse(event) {
    event.preventDefault();

    const submitButton = event.target.querySelector('button[type="submit"]');
    const warehouseData = {
        name: document.getElementById('warehouse-location').value
    };

    try {
        await apiRequestWithButton('/api/warehouses', {
            method: 'POST',
            body: JSON.stringify(warehouseData)
        }, submitButton);

        showSuccess('Warehouse created successfully!');
        closeModalAndCleanup('warehouse-modal');
        event.target.reset();
        warehouses = []; // Reset cache
        loadWarehouses();
        loadDashboardData();
    } catch (error) {
        // Button state is automatically reset by apiRequestWithButton
        if (error.isNetworkError) {
            showError('Server connection failed. Please check your network connection.');
        } else if (error.isCorsError) {
            showError('Server configuration error. Please contact administrator.');
        } else {
            showError('Failed to create warehouse: ' + (error.message || 'Unknown error'));
        }
    }
}

function openCustomerModal() {
    openModal('customer-modal');
}

function openEditCustomerModal(customerId) {
    const customer = customers.find(c => c.customer_id === customerId);
    if (!customer) {
        showError('Customer data not found. Refreshing list.');
        customers = [];
        loadCustomers();
        return;
    }
    document.getElementById('edit-customer-id').value = customer.customer_id;
    document.getElementById('edit-customer-name').value = customer.name || '';
    document.getElementById('edit-customer-email').value = customer.email || '';
    document.getElementById('edit-customer-phone').value = customer.phone || '';
    document.getElementById('edit-customer-address').value = customer.address || '';
    openModal('edit-customer-modal');
}

async function handleUpdateCustomer(event) {
    event.preventDefault();
    const customerId = parseInt(document.getElementById('edit-customer-id').value, 10);
    if (!customerId) {
        showError('Invalid customer selected');
        return;
    }

    const payload = {
        name: document.getElementById('edit-customer-name').value,
        email: document.getElementById('edit-customer-email').value || null,
        phone: document.getElementById('edit-customer-phone').value || null,
        address: document.getElementById('edit-customer-address').value || null,
    };

    try {
        await apiRequest(`/api/customers/${customerId}`, {
            method: 'PATCH',
            body: JSON.stringify(payload)
        });

        showSuccess('Customer updated');
        closeModal('edit-customer-modal');
        customers = [];
        loadCustomers();
        loadDashboardData();
    } catch (error) {
        showError(error.detail || 'Failed to update customer');
    }
}

async function handleCreateCustomer(event) {
    event.preventDefault();
    const payload = {
        name: document.getElementById('customer-name').value,
        email: document.getElementById('customer-email').value || null,
        phone: document.getElementById('customer-phone').value || null,
        address: document.getElementById('customer-address').value || null,
    };
    try {
        await apiRequest('/api/customers', { method: 'POST', body: JSON.stringify(payload) });
        showSuccess('Customer created');
        closeModal('customer-modal');
        event.target.reset();
        customers = [];
        loadCustomers();
    } catch (error) {
        showError(error.detail || 'Failed to create customer');
    }
}

function populateCustomerSelect() {
    const select = document.getElementById('sale-customer');
    if (!select) return;
    select.innerHTML = '<option value="">No Customer</option>';
    (customers || []).forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.customer_id;
        opt.textContent = `${c.name} ${c.phone ? '(' + c.phone + ')' : ''}`;
        select.appendChild(opt);
    });
}

async function viewCustomer(customerId) {
    try {
        const data = await apiRequest(`/api/customers/${customerId}`);
        const detailDiv = document.getElementById('customer-detail-content');
        const purchases = data.purchases || [];
        const purchasesHTML = purchases.length === 0 ? '<p>No purchases yet.</p>' : `
            <table>
                <thead><tr><th>Document</th><th>Total</th><th>Date</th></tr></thead>
                <tbody>
                    ${purchases.map(p => `
                        <tr><td>${p.document_id}</td><td>$${p.total_value.toFixed(2)}</td><td>${new Date(p.created_at).toLocaleString()}</td></tr>
                    `).join('')}
                </tbody>
            </table>`;

        detailDiv.innerHTML = `
            <p><strong>Name:</strong> ${data.name}</p>
            <p><strong>Contact:</strong> ${data.email || ''} ${data.phone || ''}</p>
            <p><strong>Address:</strong> ${data.address || ''}</p>
            <p><strong>Debt Balance:</strong> $${(data.debt_balance || 0).toFixed(2)}</p>
            <div style="margin:12px 0;">
                <input type="number" id="payment-amount" placeholder="Payment amount (use negative to reduce debt)" style="width:60%;padding:8px;">
                <button class="btn-secondary" onclick="recordCustomerPayment(${customerId})">Apply</button>
            </div>
            <h4>Purchase History</h4>
            ${purchasesHTML}
        `;
        openModal('customer-detail-modal');
    } catch (error) {
        showError(error.detail || 'Failed to load customer');
    }
}

async function recordCustomerPayment(customerId) {
    const amountInput = document.getElementById('payment-amount');
    const val = parseFloat(amountInput.value);
    if (isNaN(val)) {
        showError('Enter a valid amount');
        return;
    }
    try {
        await apiRequest(`/api/customers/${customerId}/debt`, { method: 'PATCH', body: JSON.stringify({ amount: val }) });
        showSuccess('Debt updated');
        loadCustomers();
        viewCustomer(customerId);
    } catch (error) {
        showError(error.detail || 'Failed to update debt');
    }
}

async function handleCreateDocument(event) {
    event.preventDefault();

    const docType = document.getElementById('doc-type').value;
    const documentData = {
        doc_type: docType,
        items: []
    };

    // Add warehouse info based on type
    if (docType === 'import') {
        documentData.destination_warehouse_id = parseInt(document.getElementById('dest-warehouse').value);
    } else if (docType === 'export' || docType === 'sale') {
        documentData.source_warehouse_id = parseInt(document.getElementById('source-warehouse').value);
    } else if (docType === 'transfer') {
        documentData.source_warehouse_id = parseInt(document.getElementById('source-warehouse').value);
        documentData.destination_warehouse_id = parseInt(document.getElementById('dest-warehouse').value);
    }

    if (docType === 'sale') {
        const customerId = document.getElementById('sale-customer')?.value;
        if (customerId) documentData.customer_id = parseInt(customerId);
    }

    // Collect items
    const itemRows = document.querySelectorAll('.item-row');
    itemRows.forEach(row => {
        const productSelect = row.querySelector('.product-select');
        const quantityInput = row.querySelector('.quantity-input');
        const priceInput = row.querySelector('.price-input');

        if (productSelect.value && quantityInput.value) {
            const item = {
                product_id: parseInt(productSelect.value),
                quantity: parseInt(quantityInput.value)
            };
            if (docType === 'import') {
                item.unit_price = priceInput.value ? parseFloat(priceInput.value) : 0;
            } else if (docType === 'export' || docType === 'sale') {
                item.unit_price = priceInput.value ? parseFloat(priceInput.value) : 0;
            } else if (docType === 'transfer') {
                item.unit_price = 0;
            }
            documentData.items.push(item);
        }
    });

    if (documentData.items.length === 0) {
        showError('Please add at least one item to the document');
        return;
    }

    try {
        // Route to correct endpoint based on document type
        const endpoint = `/api/documents/${docType}`;
        const response = await apiRequest(endpoint, {
            method: 'POST',
            body: JSON.stringify(documentData)
        });

        showSuccess('Document created successfully!');
        closeModal('document-modal');
        event.target.reset();
        documents = []; // Reset cache
        loadDocuments();
        loadDashboardData();
    } catch (error) {
        console.error('Document creation error:', error);
        showError(error.detail || 'Failed to create document');
    }
}

async function handleCreateUser(event) {
    console.log('handleCreateUser called');
    event.preventDefault();
    
    const emailInput = document.getElementById('create-user-email');
    const passwordInput = document.getElementById('create-user-password');
    const roleInput = document.getElementById('create-user-role');
    
    const email = emailInput.value;
    const password = passwordInput.value;
    const role = roleInput.value;
    
    const payload = { email, password, role, full_name: null };
    console.log('Creating user with payload:', payload);
    
    try {
        const response = await apiRequest('/api/users', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        console.log('User creation response:', response);
        
        // IMMEDIATELY clear sensitive fields to prevent password manager popup
        console.log('Clearing form fields immediately...');
        emailInput.value = '';
        passwordInput.value = '';
        roleInput.value = 'user';
        
        // IMMEDIATELY close modal
        console.log('Closing modal...');
        closeModal('user-modal');
        
        // Small delay to ensure modal is closed before showing success
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Show success message
        console.log('Showing success message');
        showSuccess('User created successfully');
        
        // Load users in background
        console.log('Loading users in background...');
        await loadUsersAndRender();
        console.log('Users loaded successfully');
        
    } catch (e) {
        console.error('User creation error:', e);
        
        // Clear form fields even on error
        emailInput.value = '';
        passwordInput.value = '';
        roleInput.value = 'user';
        
        // Close modal to unblock UI
        closeModal('user-modal');
        
        // Extract meaningful error message
        let errorMsg = 'Failed to create user';
        if (e && typeof e === 'object') {
            if (Array.isArray(e.detail)) {
                const errors = e.detail.map(err => {
                    if (typeof err === 'object' && err.msg) {
                        return `${err.loc?.join('.')} - ${err.msg}`;
                    }
                    return String(err);
                });
                errorMsg = errors.join('; ');
            } else if (e.message && e.message !== '[object Object],[object Object]') {
                errorMsg = e.message;
            } else if (e.detail) {
                errorMsg = typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail);
            } else if (e.error) {
                errorMsg = e.error;
            }
        } else if (typeof e === 'string') {
            errorMsg = e;
        }
        console.error('Final error message:', errorMsg);
        showError(errorMsg);
    }
}

// Helper function to load and render users list
async function loadUsersAndRender() {
    try {
        console.log('loadUsersAndRender: starting');
        const usersList = document.getElementById('users-list');
        if (!usersList) {
            console.warn('users-list element not found');
            return;
        }
        
        usersList.innerHTML = '<p>Loading users...</p>';
        
        const users = await apiRequest('/api/users');
        console.log('loadUsersAndRender: received users:', users);
        
        if (users && users.length > 0) {
            console.log(`loadUsersAndRender: rendering ${users.length} users`);
            
            // Create table manually to avoid inline onclick issues
            const table = document.createElement('table');
            
            // Create header
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            ['ID', 'Email', 'Role', 'Status', 'Actions'].forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);
            
            // Create body
            const tbody = document.createElement('tbody');
            users.forEach(u => {
                const row = document.createElement('tr');
                
                // ID
                const tdId = document.createElement('td');
                tdId.textContent = u.user_id;
                row.appendChild(tdId);
                
                // Email
                const tdEmail = document.createElement('td');
                tdEmail.textContent = u.email;
                row.appendChild(tdEmail);
                
                // Role
                const tdRole = document.createElement('td');
                tdRole.textContent = u.role;
                row.appendChild(tdRole);
                
                // Status
                const tdStatus = document.createElement('td');
                tdStatus.textContent = u.is_active ? 'Active' : 'Inactive';
                row.appendChild(tdStatus);
                
                // Actions
                const tdActions = document.createElement('td');
                
                // Manage button
                const manageBtn = document.createElement('button');
                manageBtn.className = 'btn-secondary';
                manageBtn.textContent = 'Manage';
                manageBtn.onclick = () => openManageUserModal(u.user_id);
                tdActions.appendChild(manageBtn);
                
                // Delete button
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn-danger';
                deleteBtn.textContent = 'Delete';
                deleteBtn.onclick = () => deleteUserConfirm(u.user_id, u.email);
                tdActions.appendChild(deleteBtn);
                
                row.appendChild(tdActions);
                tbody.appendChild(row);
            });
            table.appendChild(tbody);
            
            usersList.innerHTML = '';
            usersList.appendChild(table);
            console.log('loadUsersAndRender: table rendered successfully');
        } else {
            console.log('loadUsersAndRender: no users found');
            usersList.innerHTML = '<p>No users found.</p>';
        }
    } catch (loadError) {
        console.error('Error loading users after creation:', loadError);
    }
}

// Delete user account
async function deleteUserConfirm(userId, userEmail) {
    // Confirm deletion
    const confirmDelete = confirm(`Are you sure you want to delete user "${userEmail}"? This action cannot be undone.`);
    if (!confirmDelete) return;
    
    try {
        console.log(`Deleting user ${userId} (${userEmail})`);
        await apiRequest(`/api/users/${userId}`, {
            method: 'DELETE'
        });
        
        console.log(`User ${userId} deleted successfully`);
        showSuccess(`User "${userEmail}" deleted successfully`);
        
        // Reload users list
        await loadUsersAndRender();
        
    } catch (e) {
        console.error('User deletion error:', e);
        
        let errorMsg = `Failed to delete user "${userEmail}"`;
        if (e && typeof e === 'object') {
            if (Array.isArray(e.detail)) {
                const errors = e.detail.map(err => {
                    if (typeof err === 'object' && err.msg) {
                        return err.msg;
                    }
                    return String(err);
                });
                errorMsg = errors.join('; ');
            } else if (e.message) {
                errorMsg = e.message;
            } else if (e.detail) {
                errorMsg = typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail);
            }
        }
        showError(errorMsg);
    }
}

// Modal functions
function showCreateProductModal() {
    openModal('product-modal');
}

function showCreateWarehouseModal() {
    openModal('warehouse-modal');
}

async function refreshProductsCache() {
    const res = await apiRequest('/api/products');
    products = res || [];
}

async function refreshWarehousesCache() {
    const res = await apiRequest('/api/warehouses');
    warehouses = res || [];
}

async function showCreateDocumentModal() {
    await Promise.all([refreshWarehousesCache(), refreshProductsCache()]);
    updateWarehouseDropdowns();
    updateProductDropdowns();
    loadCustomers();
    resetDocumentForm();
    openModal('document-modal');
}

function openUserModal() {
    openModal('user-modal');
}

function resetDocumentForm() {
    const form = document.getElementById('document-form');
    if (form) form.reset();

    const itemsContainer = document.getElementById('document-items');
    if (itemsContainer) {
        const rows = itemsContainer.querySelectorAll('.item-row');
        rows.forEach((row, idx) => {
            if (idx === 0) {
                const productSelect = row.querySelector('.product-select');
                const quantityInput = row.querySelector('.quantity-input');
                const priceInput = row.querySelector('.price-input');
                if (productSelect) productSelect.value = '';
                if (quantityInput) quantityInput.value = '';
                if (priceInput) priceInput.value = '';
            } else {
                row.remove();
            }
        });
    }

    updateProductDropdowns();
    updateDocumentForm();
}

async function openManageUserModal(preselectUserId) {
    // Build modal if not exists
    let modal = document.getElementById('manage-user-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'manage-user-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content large-modal">
                <span class="close" onclick="closeModal('manage-user-modal')">&times;</span>
                <h2>Manage Roles & Permissions</h2>
                <div class="form-group">
                    <label for="manage-user-select">Select User</label>
                    <select id="manage-user-select"></select>
                </div>
                <div class="form-group">
                    <label for="manage-role-select">Role</label>
                    <select id="manage-role-select"></select>
                </div>
                <div class="form-group">
                    <label>Permissions (override)</label>
                    <div id="permissions-checkboxes" style="display:grid;grid-template-columns:repeat(2, minmax(200px, 1fr));gap:8px;"></div>
                    <small>Leave all unchecked to use role defaults.</small>
                </div>
                <div style="margin-top: 16px; display:flex; gap:8px; justify-content:flex-end;">
                    <button class="btn-secondary" onclick="closeModal('manage-user-modal')">Cancel</button>
                    <button class="btn-secondary" onclick="clearUserOverrides()">Clear Overrides</button>
                    <button class="btn-primary" onclick="saveUserPermissions()">Save</button>
                </div>
            </div>`;
        document.body.appendChild(modal);
    }

    // Load users and permissions
    const [usersRes, permsRes] = await Promise.all([
        apiRequest('/api/users'),
        apiRequest('/api/users/permissions')
    ]);

    // Populate user list
    const userSelect = document.getElementById('manage-user-select');
    userSelect.innerHTML = usersRes.map(u => `<option value="${u.user_id}">${u.email}</option>`).join('');
    if (preselectUserId) userSelect.value = String(preselectUserId);

    // Populate roles
    const roleSelect = document.getElementById('manage-role-select');
    const roles = Object.keys(permsRes.roles);
    roleSelect.innerHTML = roles.map(r => `<option value="${r}">${r}</option>`).join('');

    // Populate permissions checkboxes
    const permsDiv = document.getElementById('permissions-checkboxes');
    permsDiv.innerHTML = permsRes.permissions.map(p => `
        <label><input type="checkbox" value="${p}"> ${p}</label>
    `).join('');

    // Show modal
    modal.style.display = 'block';
}

async function saveUserPermissions() {
    const userId = parseInt(document.getElementById('manage-user-select').value);
    const role = document.getElementById('manage-role-select').value;
    const checkboxes = Array.from(document.querySelectorAll('#permissions-checkboxes input[type=checkbox]'));
    const selected = checkboxes.filter(c => c.checked).map(c => c.value);

    // Update role
    await apiRequest(`/api/users/${userId}/role`, {
        method: 'PATCH',
        body: JSON.stringify({ role })
    });

    // Update overrides
    await apiRequest(`/api/users/${userId}/permissions`, {
        method: 'PATCH',
        body: JSON.stringify({ permissions: selected, mode: 'override' })
    });

    showSuccess('User permissions saved');
    closeModal('manage-user-modal');
    loadUsers();
}

async function clearUserOverrides() {
    const userId = parseInt(document.getElementById('manage-user-select').value);
    await apiRequest(`/api/users/${userId}/permissions`, {
        method: 'PATCH',
        body: JSON.stringify({ mode: 'clear' })
    });
    showSuccess('Overrides cleared');
}

function openChangePasswordModal() {
    openModal('change-password-modal');
}

async function handleChangePassword(event) {
    event.preventDefault();
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;

    if (newPassword !== confirmPassword) {
        showError('New passwords do not match');
        return;
    }

    if (newPassword.length < 6) {
        showError('Password must be at least 6 characters');
        return;
    }

    try {
        await apiRequest('/api/users/me/change-password', {
            method: 'POST',
            body: JSON.stringify({ old_password: currentPassword, new_password: newPassword })
        });
        showSuccess('Password changed successfully');
        closeModal('change-password-modal');
        event.target.reset();
    } catch (e) {
        showError('Failed to change password. Check your current password.');
    }
}

function closeAllModals() {
    console.log('Closing all modals');
    const allModals = document.querySelectorAll('.modal');
    allModals.forEach(modal => {
        modal.style.display = 'none';
        modal.style.visibility = 'hidden';
        modal.style.opacity = '0';
        modal.style.pointerEvents = 'none';
    });
}

// Helper function to manage button states during API requests
function setButtonLoading(button, loading = true) {
    if (!button) return;
    
    if (loading) {
        // Store original text if not already stored
        if (!button.originalText) {
            button.originalText = button.textContent;
        }
        button.disabled = true;
        button.classList.add('loading');
        button.textContent = 'Loading...';
    } else {
        button.disabled = false;
        button.classList.remove('loading');
        // Restore original text
        if (button.originalText) {
            button.textContent = button.originalText;
            delete button.originalText;
        }
    }
}

// Helper function to handle API requests with proper button management
async function apiRequestWithButton(endpoint, options = {}, buttonElement = null) {
    try {
        if (buttonElement) {
            setButtonLoading(buttonElement, true);
        }
        
        const response = await apiRequest(endpoint, options);
        return response;
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    } finally {
        if (buttonElement) {
            setButtonLoading(buttonElement, false);
        }
    }
}

// Helper function to close modal and clean up state
function closeModalAndCleanup(modalId) {
    closeModal(modalId);
    
    // Additional cleanup for any global state
    if (window.activeRequests) {
        window.activeRequests.forEach(controller => {
            if (controller && !controller.signal.aborted) {
                controller.abort();
            }
        });
        window.activeRequests = [];
    }
}

function closeModal(modalId) {
    try {
        const modal = document.getElementById(modalId);
        if (modal) {
            console.log(`Closing modal: ${modalId}`);
            
            // Remove any active form validation states
            const forms = modal.querySelectorAll('form');
            forms.forEach(form => {
                if (form) {
                    form.reset();
                    // Clear any validation error states
                    const inputs = form.querySelectorAll('input, select, textarea');
                    inputs.forEach(input => {
                        input.classList.remove('error');
                    });
                }
            });
            
            // Reset all buttons in the modal to enabled state
            const buttons = modal.querySelectorAll('button');
            buttons.forEach(button => {
                button.disabled = false;
                button.classList.remove('loading');
                // Remove any loading text/spinners
                if (button.originalText) {
                    button.textContent = button.originalText;
                    delete button.originalText;
                }
            });
            
            // Set all display properties to ensure it's truly hidden
            modal.style.display = 'none';
            modal.style.visibility = 'hidden';
            modal.style.opacity = '0';
            modal.style.pointerEvents = 'none';
            modal.setAttribute('aria-hidden', 'true');

            // Clear any global state that might interfere
            if (window.currentEditingItem) {
                window.currentEditingItem = null;
            }

            if (modalId === 'view-document-modal' && documentAutoRefreshHandle) {
                clearInterval(documentAutoRefreshHandle);
                documentAutoRefreshHandle = null;
            }

            // Clean up any backdrop elements (for custom modal implementation)
            const backdrops = document.querySelectorAll('.modal-backdrop');
            backdrops.forEach(backdrop => {
                backdrop.remove();
            });

            // Remove any lingering backdrop-related classes from body
            document.body.classList.remove('modal-open');
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';

            // Force a small delay to ensure DOM updates are complete
            setTimeout(() => {
                console.log(`Modal hidden and DOM updated`);
                // Trigger a custom event to notify that modal is closed
                const event = new CustomEvent('modalClosed', { detail: { modalId } });
                document.dispatchEvent(event);
            }, 10);
            
        } else {
            console.warn(`Modal not found: ${modalId}`);
        }
    } catch (e) {
        console.error('Error closing modal:', e);
    }
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        console.log(`Opening modal: ${modalId}`);
        // First close all other modals
        closeAllModals();
        
        // Reset any button states in the modal
        const buttons = modal.querySelectorAll('button');
        buttons.forEach(button => {
            button.disabled = false;
            button.classList.remove('loading');
        });
        
        // Then open this one
        modal.style.display = 'block';
        modal.style.visibility = 'visible';
        modal.style.opacity = '1';
        modal.style.pointerEvents = 'auto';
        modal.setAttribute('aria-hidden', 'false');
        
        // Add a small delay to ensure the modal is fully rendered
        setTimeout(() => {
            // Focus the first input if available
            const firstInput = modal.querySelector('input, select, textarea, button');
            if (firstInput && firstInput.tagName !== 'BUTTON') {
                firstInput.focus();
            }
        }, 100);
    } else {
        console.error(`Modal not found: ${modalId}`);
    }
}

function updateDocumentForm() {
    const docType = document.getElementById('doc-type').value;
    const sourceGroup = document.getElementById('source-warehouse-group');
    const destGroup = document.getElementById('dest-warehouse-group');
    const priceInputs = document.querySelectorAll('.price-input');
    const customerGroup = document.getElementById('customer-group');

    if (docType === 'import') {
        sourceGroup.style.display = 'none';
        destGroup.style.display = 'block';
        priceInputs.forEach(inp => { inp.required = false; inp.style.display = ''; });
        if (customerGroup) customerGroup.style.display = 'none';
    } else if (docType === 'export') {
        sourceGroup.style.display = 'block';
        destGroup.style.display = 'none';
        priceInputs.forEach(inp => { inp.required = false; inp.style.display = ''; });
        if (customerGroup) customerGroup.style.display = 'none';
    } else if (docType === 'transfer') {
        sourceGroup.style.display = 'block';
        destGroup.style.display = 'block';
        priceInputs.forEach(inp => { inp.required = false; inp.style.display = 'none'; inp.value = ''; });
        if (customerGroup) customerGroup.style.display = 'none';
    } else if (docType === 'sale') {
        sourceGroup.style.display = 'block';
        destGroup.style.display = 'none';
        priceInputs.forEach(inp => { inp.required = false; inp.style.display = ''; });
        if (customerGroup) customerGroup.style.display = 'block';
    }
}

function updateWarehouseDropdowns() {
    const warehouseSelects = ['source-warehouse', 'dest-warehouse'];

    warehouseSelects.forEach(selectId => {
        const select = document.getElementById(selectId);
        select.innerHTML = '<option value="">Select Warehouse</option>';

        warehouses.forEach(warehouse => {
            const option = document.createElement('option');
            option.value = warehouse.warehouse_id;
            option.textContent = `${warehouse.warehouse_id} - ${(warehouse.name || warehouse.location)}`;
            select.appendChild(option);
        });
    });
}

function updateProductDropdowns() {
    const productSelects = document.querySelectorAll('.product-select');

    productSelects.forEach(select => {
        // Only populate if this select is empty (no options except placeholder)
        if (select.options.length <= 1 || (select.options.length === 1 && select.options[0].value === '')) {
            const currentValue = select.value;
            select.innerHTML = '<option value="">Select Product</option>';

            products.forEach(product => {
                const option = document.createElement('option');
                option.value = product.product_id;
                option.textContent = `${product.product_id} - ${product.name}`;
                select.appendChild(option);
            });
            
            // Restore the previously selected value if it exists
            if (currentValue) {
                select.value = currentValue;
            }
        }
    });
}

function addItem() {
    const itemsContainer = document.getElementById('document-items');
    const itemRow = document.createElement('div');
    itemRow.className = 'item-row';

    itemRow.innerHTML = `
        <select class="product-select" required>
            <option value="">Select Product</option>
        </select>
        <input type="number" class="quantity-input" placeholder="Quantity" min="1" required>
        <input type="number" class="price-input" placeholder="Unit Price" step="0.01">
        <button type="button" class="btn-secondary" onclick="removeItem(this)">Remove</button>
    `;

    itemsContainer.appendChild(itemRow);
    updateProductDropdowns();
}

function removeItem(button) {
    button.closest('.item-row').remove();
}

// Report functions
// Report Modal Functions
function openInventoryReportModal() {
    populateWarehouseFilter('inventory-warehouse-filter');
    populateProductFilter('inventory-product-filter');
    openModal('inventory-report-modal');
}

function openProductReportModal() {
    populateProductFilter('product-filter');
    openModal('product-report-modal');
}

function openDocumentReportModal() {
    openModal('document-report-modal');
}

function openWarehouseReportModal() {
    populateWarehouseFilter('warehouse-filter');
    openModal('warehouse-report-modal');
}

async function openCustomerSalesReportModal() {
    console.log('Opening customer sales report modal...');
    console.log('Customers array:', customers);
    
    // Load customers if not already loaded
    if (customers.length === 0) {
        try {
            const response = await apiRequest('/api/customers');
            if (response) customers = response;
        } catch (error) {
            console.error('Failed to load customers:', error);
        }
    }
    
    populateCustomerFilter('sales-customer-filter');
    await populateSalespersonFilter('sales-salesperson-filter');
    openModal('customer-sales-report-modal');
}

function populateWarehouseFilter(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    // Clear existing options except the first one
    while (select.options.length > 1) {
        select.remove(1);
    }
    
    warehouses.forEach(warehouse => {
        const option = document.createElement('option');
        option.value = warehouse.warehouse_id;
        option.textContent = `${warehouse.warehouse_id} - ${(warehouse.name || warehouse.location)}`;
        select.appendChild(option);
    });
}

function populateProductFilter(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    // Clear existing options except the first one
    while (select.options.length > 1) {
        select.remove(1);
    }
    
    products.forEach(product => {
        const option = document.createElement('option');
        option.value = product.product_id;
        option.textContent = `${product.product_id} - ${product.name}`;
        select.appendChild(option);
    });
}

function populateCustomerFilter(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    // Clear existing options except the first one
    while (select.options.length > 1) {
        select.remove(1);
    }
    
    customers.forEach(customer => {
        const option = document.createElement('option');
        option.value = customer.customer_id;
        option.textContent = `${customer.customer_id} - ${customer.name}`;
        select.appendChild(option);
    });
}

async function populateSalespersonFilter(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    try {
        // Get all users (salespersons are users who can create documents)
        const users = await apiRequest('/api/users');
        if (!users || users.length === 0) return;
        
        // Extract unique user emails
        const salespersons = [...new Set(users.map(user => user.email).filter(Boolean))];
        
        // Clear existing options except the first one
        while (select.options.length > 1) {
            select.remove(1);
        }
        
        // Add salesperson options
        salespersons.forEach(salesperson => {
            const option = document.createElement('option');
            option.value = salesperson;
            option.textContent = salesperson;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load salespersons:', error);
    }
}

async function generateInventoryReport() {
    try {
        const warehouseId = document.getElementById('inventory-warehouse-filter')?.value;
        const productId = document.getElementById('inventory-product-filter')?.value;
        const dateFrom = document.getElementById('inventory-date-from')?.value;
        const dateTo = document.getElementById('inventory-date-to')?.value;

        let url = '/api/reports/inventory/list';
        const params = new URLSearchParams();
        
        if (warehouseId) params.append('warehouse_id', warehouseId);
        if (dateFrom) params.append('start_date', dateFrom);
        if (dateTo) params.append('end_date', dateTo);
        
        if (params.toString()) {
            url += '?' + params.toString();
        }

        console.log('Generating inventory report from:', url);
        const response = await apiRequest(url);
        console.log('Report response:', response);
        displayInventoryReport(response);
        closeModal('inventory-report-modal');
    } catch (error) {
        console.error('Inventory report error:', error);
        const message = error.detail || error.message || 'Failed to generate inventory report. Please check your filters and try again.';
        showError(message);
    }
}

async function generateProductReport() {
    try {
        const dateFrom = document.getElementById('product-date-from')?.value;
        const dateTo = document.getElementById('product-date-to')?.value;

        let url = '/api/products';
        const params = new URLSearchParams();
        
        if (dateFrom) params.append('start_date', dateFrom);
        if (dateTo) params.append('end_date', dateTo);
        
        if (params.toString()) {
            url += '?' + params.toString();
        }

        console.log('Generating product report from:', url);
        const response = await apiRequest(url);
        console.log('Report response:', response);
        displayProductReport(response);
        closeModal('product-report-modal');
    } catch (error) {
        console.error('Product report error:', error);
        const message = error.detail || error.message || 'Failed to generate product report. Please check your filters and try again.';
        showError(message);
    }
}

async function generateDocumentReport() {
    try {
        const docType = document.getElementById('document-type-filter')?.value;
        const status = document.getElementById('document-status-filter')?.value;
        const dateFrom = document.getElementById('document-date-from')?.value;
        const dateTo = document.getElementById('document-date-to')?.value;

        let url = '/api/reports/documents';
        const params = new URLSearchParams();
        
        if (dateFrom) params.append('start_date', dateFrom);
        if (dateTo) params.append('end_date', dateTo);
        
        if (params.toString()) {
            url += '?' + params.toString();
        }

        console.log('Generating document report from:', url);
        const response = await apiRequest(url);
        console.log('Report response:', response);
        displayDocumentReport(response);
        closeModal('document-report-modal');
    } catch (error) {
        console.error('Document report error:', error);
        const message = error.detail || error.message || 'Failed to generate transaction report. Please check your filters and try again.';
        showError(message);
    }
}

async function generateWarehouseReport() {
    try {
        const warehouseId = document.getElementById('warehouse-filter')?.value;
        const dateFrom = document.getElementById('warehouse-date-from')?.value;
        const dateTo = document.getElementById('warehouse-date-to')?.value;

        let url = warehouseId ? `/api/reports/warehouse/${warehouseId}` : '/api/warehouses';
        const params = new URLSearchParams();
        
        if (dateFrom) params.append('start_date', dateFrom);
        if (dateTo) params.append('end_date', dateTo);
        
        if (params.toString()) {
            url += '?' + params.toString();
        }

        console.log('Generating warehouse report from:', url);
        const response = await apiRequest(url);
        console.log('Report response:', response);
        displayWarehouseReport(response);
        closeModal('warehouse-report-modal');
    } catch (error) {
        console.error('Warehouse report error:', error);
        const message = error.detail || error.message || 'Failed to generate warehouse report. Please check your filters and try again.';
        showError(message);
    }
}

async function generateCustomerSalesReport() {
    try {
        const customerId = document.getElementById('sales-customer-filter')?.value;
        const salesperson = document.getElementById('sales-salesperson-filter')?.value;
        const dateFrom = document.getElementById('sales-date-from')?.value;
        const dateTo = document.getElementById('sales-date-to')?.value;

        let url = '/api/reports/sales';
        const params = new URLSearchParams();
        
        if (customerId) params.append('customer_id', customerId);
        if (salesperson) params.append('salesperson', salesperson);
        if (dateFrom) params.append('start_date', dateFrom);
        if (dateTo) params.append('end_date', dateTo);
        
        if (params.toString()) {
            url += '?' + params.toString();
        }

        console.log('Generating customer sales report from:', url);
        const response = await apiRequest(url);
        console.log('Sales report response:', response);
        displayCustomerSalesReport(response);
        closeModal('customer-sales-report-modal');
    } catch (error) {
        console.error('Customer sales report error:', error);
        const message = error.detail || error.message || 'Failed to generate customer sales report. Please check your filters and try again.';
        showError(message);
    }
}


function displayCustomerSalesReport(data) {
    const resultsDiv = document.getElementById('report-results');
    
    if (!data || !data.summary) {
        resultsDiv.innerHTML = '<p>No sales data found</p>';
        return;
    }

    const summary = data.summary;
    const sales = data.sales || [];

    let html = `
        <div class="report-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
            <h2 style="margin: 0;">💰 Customer Sales Report</h2>
            <div style="display: flex; gap: 8px;">
                <button onclick="exportCurrentReportAsExcel()" class="btn-primary" style="padding: 8px 16px;">📥 Export to Excel</button>
                <button onclick="exportCurrentReportAsCSV()" class="btn-secondary" style="padding: 8px 16px;">📄 Export to CSV</button>
            </div>
        </div>
        <div class="report-summary">
            <div class="summary-card">
                <h3>$${summary.total_sales.toLocaleString('en-US', {minimumFractionDigits: 2})}</h3>
                <p>Total Sales</p>
            </div>
            <div class="summary-card">
                <h3>$${summary.total_debt.toLocaleString('en-US', {minimumFractionDigits: 2})}</h3>
                <p>Total Outstanding Debt</p>
            </div>
            <div class="summary-card">
                <h3>${summary.transaction_count}</h3>
                <p>Transactions</p>
            </div>
            <div class="summary-card">
                <h3>${summary.unique_customers}</h3>
                <p>Customers</p>
            </div>
        </div>
    `;

    if (summary.period && (summary.period.start || summary.period.end)) {
        html += '<div class="report-period">';
        if (summary.period.start && summary.period.end) {
            html += `<p>Period: ${summary.period.start} to ${summary.period.end}</p>`;
        } else if (summary.period.start) {
            html += `<p>From: ${summary.period.start}</p>`;
        } else if (summary.period.end) {
            html += `<p>Until: ${summary.period.end}</p>`;
        }
        html += '</div>';
    }

    if (sales.length === 0) {
        html += '<p>No sales transactions found for the selected criteria.</p>';
    } else {
        html += `
            <div class="report-table-wrapper">
                <table class="report-table">
                    <thead>
                        <tr>
                            <th>Doc ID</th>
                            <th>Date</th>
                            <th>Customer</th>
                            <th>Salesperson</th>
                            <th>Sale Amount</th>
                            <th>Customer Debt</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        sales.forEach(sale => {
            const saleDate = sale.sale_date ? new Date(sale.sale_date).toLocaleDateString() : 'N/A';
            html += `
                <tr>
                    <td>${sale.document_id}</td>
                    <td>${saleDate}</td>
                    <td>${sale.customer_name}</td>
                    <td>${sale.salesperson}</td>
                    <td class="amount">$${sale.total_sale.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                    <td class="amount ${sale.customer_debt > 0 ? 'text-warning' : ''}">
                        $${sale.customer_debt.toLocaleString('en-US', {minimumFractionDigits: 2})}
                    </td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;
    }

    resultsDiv.innerHTML = html;
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

function displayReportResults(title, data) {
    const resultsDiv = document.getElementById('report-results');

    console.log('Report data:', data);

    // Handle both array and object responses
    let records = Array.isArray(data) ? data : (data?.records || data?.data || data?.items || []);
    
    if (!records || records.length === 0) {
        resultsDiv.innerHTML = `<div class="report-container"><h3>${title}</h3><div class="report-empty"><p>No data available for the selected criteria.</p></div></div>`;
        return;
    }

    let html = `<div class="report-container"><h3>${title}</h3>`;

    if (Array.isArray(records)) {
        // Build professional table
        html += '<table class="report-table"><thead><tr>';
        const keys = Object.keys(records[0]).filter(k => k !== 'id'); // Hide internal IDs
        keys.forEach(key => {
            const header = key.replace(/_/g, ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            html += `<th>${header}</th>`;
        });
        html += '</tr></thead><tbody>';

        records.forEach(item => {
            html += '<tr>';
            keys.forEach(key => {
                let value = item[key];
                // Format values professionally
                if (value === null || value === undefined) {
                    value = '—';
                } else if (typeof value === 'number' && key.includes('price')) {
                    value = '$' + parseFloat(value).toFixed(2);
                } else if (typeof value === 'number' && key.includes('quantity')) {
                    value = Math.round(value);
                } else if (key.includes('date') || key.includes('created') || key.includes('updated')) {
                    try {
                        value = new Date(value).toLocaleDateString('en-US', {year: 'numeric', month: 'short', day: 'numeric'});
                    } catch (e) {
                        // Keep original value if date parsing fails
                    }
                } else if (typeof value === 'boolean') {
                    value = value ? '✓ Yes' : '✗ No';
                }
                html += `<td>${value}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        
        // Add summary and export button
        html += `<div class="report-footer"><div class="report-summary"><p><strong>Total Records:</strong> ${records.length}</p></div><button class="btn-primary" onclick="exportCurrentReport()">📥 Export to Excel</button></div>`;
    } else {
        html += `<div class="report-data"><pre>${JSON.stringify(records, null, 2)}</pre></div>`;
    }
    
    html += '</div>';
    resultsDiv.innerHTML = html;
}

function displayProductReport(data) {
    const resultsDiv = document.getElementById('report-results');

    console.log('Product report data:', data);

    // Handle both array and object responses
    let products = Array.isArray(data) ? data : (data?.products || data?.data || []);

    if (!products || products.length === 0) {
        resultsDiv.innerHTML = '<div class="report-container"><h3>Product Report</h3><div class="report-empty"><p>No products found.</p></div></div>';
        return;
    }

    let html = `
        <div class="report-container">
            <div class="report-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <h3 style="margin: 0;">Product Report</h3>
                <div style="display: flex; gap: 8px;">
                    <button onclick="exportCurrentReportAsExcel()" class="btn-primary" style="padding: 8px 16px;">📥 Export to Excel</button>
                    <button onclick="exportCurrentReportAsCSV()" class="btn-secondary" style="padding: 8px 16px;">📄 Export to CSV</button>
                </div>
            </div>
    `;
    html += '<table class="report-table"><thead><tr><th>Product ID</th><th>Product Name</th><th>Price</th><th>Description</th></tr></thead><tbody>';

    let totalValue = 0;

    products.forEach(product => {
        html += '<tr>';
        html += `<td>#${product.product_id}</td>`;
        html += `<td>${product.name}</td>`;
        html += `<td>$${parseFloat(product.price).toFixed(2)}</td>`;
        html += `<td>${product.description || '—'}</td>`;
        html += '</tr>';
        totalValue += parseFloat(product.price);
    });

    html += '</tbody></table>';
    html += `<div class="report-footer"><div class="report-summary"><div class="summary-grid"><div class="summary-item"><span class="label">Total Products:</span> <span class="value">${products.length}</span></div><div class="summary-item"><span class="label">Total Catalog Value:</span> <span class="value">$${totalValue.toFixed(2)}</span></div><div class="summary-item"><span class="label">Average Price:</span> <span class="value">$${(totalValue / products.length).toFixed(2)}</span></div></div></div></div>`;
    html += '</div>';
    resultsDiv.innerHTML = html;
}

function displayInventoryReport(data) {
    const resultsDiv = document.getElementById('report-results');

    console.log('Inventory report data:', data);

    // Handle both array and object responses
    let items = Array.isArray(data) ? data : (data?.items || data?.inventory || data?.data || []);

    if (!items || items.length === 0) {
        resultsDiv.innerHTML = '<div class="report-container"><h3>Inventory Report</h3><div class="report-empty"><p>No inventory data available for the selected criteria.</p></div></div>';
        return;
    }

    let html = `
        <div class="report-container">
            <div class="report-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <h3 style="margin: 0;">Inventory Report</h3>
                <div style="display: flex; gap: 8px;">
                    <button onclick="exportCurrentReportAsExcel()" class="btn-primary" style="padding: 8px 16px;">📥 Export to Excel</button>
                    <button onclick="exportCurrentReportAsCSV()" class="btn-secondary" style="padding: 8px 16px;">📄 Export to CSV</button>
                </div>
            </div>
    `;
    html += '<table class="report-table"><thead><tr><th>Product ID</th><th>Warehouse Name</th><th>Quantity</th><th>Status</th></tr></thead><tbody>';

    let totalQuantity = 0;

    // If it's an array of inventory items
    items.forEach(item => {
        const status = item.quantity < 10 ? '<span class="warning">Low Stock</span>' : '<span class="success">In Stock</span>';
        html += '<tr>';
        html += `<td>#${item.product_id}</td>`;
        const wh = warehouses.find(w => w.warehouse_id === item.warehouse_id);
        const warehouseName = item.warehouse_name || wh?.name || wh?.location || `Warehouse ${item.warehouse_id}`;
        html += `<td>${warehouseName}</td>`;
        html += `<td>${item.quantity}</td>`;
        html += `<td>${status}</td>`;
        html += '</tr>';
        totalQuantity += item.quantity;
    });

    html += '</tbody></table>';
    html += `<div class="report-footer"><div class="report-summary"><div class="summary-grid"><div class="summary-item"><span class="label">Total Items:</span> <span class="value">${totalQuantity}</span></div><div class="summary-item"><span class="label">Total SKUs:</span> <span class="value">${items.length}</span></div></div></div></div>`;
    html += '</div>';
    resultsDiv.innerHTML = html;
}

function displayDocumentReport(data) {
    const resultsDiv = document.getElementById('report-results');

    console.log('Document report data:', data);

    // Handle both array and object responses
    let documents = Array.isArray(data) ? data : (data?.documents || data?.data || []);
    
    if (!documents || documents.length === 0) {
        resultsDiv.innerHTML = '<div class="report-container"><h3>Transaction Report</h3><div class="report-empty"><p>No transactions found for the selected criteria.</p></div></div>';
        return;
    }

    let html = `
        <div class="report-container">
            <div class="report-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <h3 style="margin: 0;">Transaction Report</h3>
                <div style="display: flex; gap: 8px;">
                    <button onclick="exportCurrentReportAsExcel()" class="btn-primary" style="padding: 8px 16px;">📥 Export to Excel</button>
                    <button onclick="exportCurrentReportAsCSV()" class="btn-secondary" style="padding: 8px 16px;">📄 Export to CSV</button>
                </div>
            </div>
    `;
    html += '<table class="report-table"><thead><tr><th>Document ID</th><th>Type</th><th>Status</th><th>Date</th><th>Items</th><th>Customer</th></tr></thead><tbody>';

    let importCount = 0, exportCount = 0, transferCount = 0, saleCount = 0;
    let draftCount = 0, postedCount = 0;

    documents.forEach(doc => {
        const docType = (doc.doc_type || 'UNKNOWN').toString().toLowerCase();
        const status = (doc.status || 'UNKNOWN').toString().toUpperCase();
        
        if (docType === 'import') {
            importCount++;
        } else if (docType === 'export') {
            exportCount++;
        } else if (docType === 'transfer') {
            transferCount++;
        } else if (docType === 'sale') {
            saleCount++;
        }
        if (status === 'DRAFT') draftCount++;
        if (status === 'POSTED') postedCount++;

        const statusClass = status === 'POSTED' ? 'status-posted' : 'status-draft';
        const date = doc.created_at ? new Date(doc.created_at).toLocaleDateString('en-US') : '—';
        
        html += '<tr>';
        html += `<td>#${doc.document_id}</td>`;
        html += `<td>${docType.charAt(0).toUpperCase() + docType.slice(1)}</td>`;
        html += `<td><span class="${statusClass}">${status}</span></td>`;
        html += `<td>${date}</td>`;
        html += `<td>${doc.item_count || 0}</td>`;
        html += `<td>${doc.customer_id ? `C-${doc.customer_id}` : '—'}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table>';
    html += `<div class="report-footer"><div class="report-summary"><div class="summary-grid"><div class="summary-item"><span class="label">Total Transactions:</span> <span class="value">${documents.length}</span></div><div class="summary-item"><span class="label">Imports:</span> <span class="value">${importCount}</span></div><div class="summary-item"><span class="label">Exports:</span> <span class="value">${exportCount}</span></div><div class="summary-item"><span class="label">Transfers:</span> <span class="value">${transferCount}</span></div><div class="summary-item"><span class="label">Sales:</span> <span class="value">${saleCount}</span></div><div class="summary-item"><span class="label">Posted:</span> <span class="value">${postedCount}</span></div><div class="summary-item"><span class="label">Draft:</span> <span class="value">${draftCount}</span></div></div></div></div>`;
    html += '</div>';
    resultsDiv.innerHTML = html;
}

function displayWarehouseReport(data) {
    const resultsDiv = document.getElementById('report-results');

    console.log('Warehouse report data:', data);

    // Handle both array and object responses
    let warehouses = Array.isArray(data) ? data : (data?.warehouses || data?.data || []);

    if (!warehouses || warehouses.length === 0) {
        resultsDiv.innerHTML = '<div class="report-container"><h3>Warehouse Report</h3><div class="report-empty"><p>No warehouse data available for the selected criteria.</p></div></div>';
        return;
    }

    let html = `
        <div class="report-container">
            <div class="report-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <h3 style="margin: 0;">Warehouse Report</h3>
                <div style="display: flex; gap: 8px;">
                    <button onclick="exportCurrentReportAsExcel()" class="btn-primary" style="padding: 8px 16px;">📥 Export to Excel</button>
                    <button onclick="exportCurrentReportAsCSV()" class="btn-secondary" style="padding: 8px 16px;">📄 Export to CSV</button>
                </div>
            </div>
    `;
    html += '<table class="report-table"><thead><tr><th>Warehouse Name</th><th>ID</th></tr></thead><tbody>';

    warehouses.forEach(warehouse => {
        html += '<tr>';
        const name = warehouse.name || warehouse.location || '—';
        html += `<td>${name}</td>`;
        html += `<td>${warehouse.warehouse_id}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table>';
    html += `<div class="report-footer"><div class="report-summary"><p><strong>Total Warehouses:</strong> ${warehouses.length}</p></div></div>`;
    html += '</div>';
    resultsDiv.innerHTML = html;
}

// Utility functions
function updateConnectionStatus(connected) {
    const statusElement = document.getElementById('connection-status');
    if (connected) {
        statusElement.textContent = '● Connected';
        statusElement.className = 'status-connected';
    } else {
        statusElement.textContent = '● Disconnected';
        statusElement.className = 'status-disconnected';
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.textContent = message;
    errorDiv.style.position = 'fixed';
    errorDiv.style.top = '20px';
    errorDiv.style.right = '20px';
    errorDiv.style.zIndex = '1001';
    document.body.appendChild(errorDiv);

    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

function showSuccess(message) {
    const successDiv = document.createElement('div');
    successDiv.className = 'success';
    successDiv.textContent = message;
    successDiv.style.position = 'fixed';
    successDiv.style.top = '20px';
    successDiv.style.right = '20px';
    successDiv.style.zIndex = '1001';
    document.body.appendChild(successDiv);

    setTimeout(() => {
        successDiv.remove();
    }, 3000);
}

function downloadCsv(filename, rows) {
    const csv = rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g,'""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function exportProductsCsv() {
    if (!products || products.length === 0) {
        showError('No products to export');
        return;
    }
    const header = ['product_id','name','price','description'];
    const rows = [header, ...products.map(p => [p.product_id, p.name, p.price, p.description || ''])];
    downloadCsv('products.csv', rows);
}

function exportInventoryCsv() {
    if (!inventory || inventory.length === 0) {
        showError('No inventory to export');
        return;
    }
    const header = ['warehouse_id','warehouse_name','product_id','quantity'];
    const rows = [header, ...inventory.map(i => [i.warehouse_id, (i.warehouse_name || ''), i.product_id, i.quantity])];
    downloadCsv('inventory.csv', rows);
}

function exportDocumentsCsv() {
    if (!documents || documents.length === 0) {
        showError('No documents to export');
        return;
    }
    const header = ['document_id','doc_type','status','created_at'];
    const rows = [header, ...documents.map(d => [d.document_id, d.doc_type, d.status, d.created_at])];
    downloadCsv('documents.csv', rows);
}

// Excel Export Functions
function exportReportToExcel(reportTitle, tableData) {
    if (!tableData || tableData.length === 0) {
        showError('No data to export');
        return;
    }

    try {
        if (typeof XLSX === 'undefined') {
            console.warn('XLSX library not loaded, falling back to CSV');
            // Fall back to CSV
            downloadCsv(`${reportTitle}.csv`, tableData);
            return;
        }
        // Create workbook
        const workbook = XLSX.utils.book_new();
        
        // Create worksheet from data
        const worksheet = XLSX.utils.aoa_to_sheet(tableData);
        
        // Set column widths
        const columnWidths = tableData[0].map(() => 18);
        worksheet['!cols'] = columnWidths.map(w => ({ wch: w }));
        
        // Add worksheet to workbook
        XLSX.utils.book_append_sheet(workbook, worksheet, reportTitle.replace(/\s+/g, '_'));
        
        // Generate filename with timestamp
        const timestamp = new Date().toISOString().slice(0, 10);
        const filename = `${reportTitle.replace(/\s+/g, '_')}_${timestamp}.xlsx`;
        
        // Write file
        XLSX.writeFile(workbook, filename);
        console.log(`Report exported as ${filename}`);
        showSuccess(`Report exported as ${filename}`);
    } catch (error) {
        console.error('Excel export error:', error);
        showError('Failed to export report to Excel: ' + error.message);
    }
}

function exportReportToCSV(reportTitle, tableData) {
    if (!tableData || tableData.length === 0) {
        // If no table data provided, try to extract from report results
        const resultsDiv = document.getElementById('report-results');
        if (!resultsDiv) {
            showError('No report data found to export');
            return;
        }
        tableData = extractTableData(resultsDiv);
    }
    
    if (!tableData || tableData.length === 0) {
        showError('No data to export');
        return;
    }

    try {
        const timestamp = new Date().toISOString().slice(0, 10);
        const filename = `${reportTitle.replace(/\s+/g, '_')}_${timestamp}.csv`;
        downloadCsv(filename, tableData);
        showSuccess(`Report exported as ${filename}`);
    } catch (error) {
        console.error('CSV export error:', error);
        showError('Failed to export report to CSV: ' + error.message);
    }
}

function extractTableData(tableElement) {
    const rows = [];
    const table = tableElement.querySelector('table');
    
    if (!table) return rows;
    
    // Extract headers
    const headers = [];
    table.querySelectorAll('thead th').forEach(th => {
        headers.push(th.textContent.trim());
    });
    if (headers.length > 0) rows.push(headers);
    
    // Extract body rows
    table.querySelectorAll('tbody tr').forEach(tr => {
        const row = [];
        tr.querySelectorAll('td').forEach(td => {
            row.push(td.textContent.trim());
        });
        if (row.length > 0) rows.push(row);
    });
    
    return rows;
}

function exportCurrentReport() {
    const resultsDiv = document.getElementById('report-results');
    // Look for h2, h3, or h1 title
    let titleElement = resultsDiv.querySelector('h2') || resultsDiv.querySelector('h3') || resultsDiv.querySelector('h1');
    const title = titleElement ? titleElement.textContent.trim().replace(/[^a-zA-Z0-9 ]/g, '') : 'Report';
    
    console.log('Exporting report with title:', title);
    
    const tableData = extractTableData(resultsDiv);
    
    if (tableData.length === 0) {
        showError('No data to export');
        return;
    }
    
    console.log('Table data extracted:', tableData.length, 'rows');
    exportReportToExcel(title, tableData);
}

// Add new export functions for Excel and CSV
function exportCurrentReportAsExcel() {
    const resultsDiv = document.getElementById('report-results');
    let titleElement = resultsDiv.querySelector('h2') || resultsDiv.querySelector('h3') || resultsDiv.querySelector('h1');
    const title = titleElement ? titleElement.textContent.trim().replace(/[^a-zA-Z0-9 ]/g, '') : 'Report';
    
    console.log('Exporting report as Excel with title:', title);
    
    const tableData = extractTableData(resultsDiv);
    
    if (tableData.length === 0) {
        showError('No data to export');
        return;
    }
    
    console.log('Table data extracted:', tableData.length, 'rows');
    exportReportToExcel(title, tableData);
}

function exportCurrentReportAsCSV() {
    const resultsDiv = document.getElementById('report-results');
    let titleElement = resultsDiv.querySelector('h2') || resultsDiv.querySelector('h3') || resultsDiv.querySelector('h1');
    const title = titleElement ? titleElement.textContent.trim().replace(/[^a-zA-Z0-9 ]/g, '') : 'Report';
    
    console.log('Exporting report as CSV with title:', title);
    
    const tableData = extractTableData(resultsDiv);
    
    if (tableData.length === 0) {
        showError('No data to export');
        return;
    }
    
    exportReportToCSV(title, tableData);
}

// Delete confirmation state
let deleteConfirmData = {
    type: null,
    id: null
};

// Edit Product Functions
async function editProduct(id) {
    const product = products.find(p => p.product_id === id);
    if (!product) {
        showError('Product not found');
        return;
    }

    document.getElementById('edit-product-name').value = product.name;
    document.getElementById('edit-product-price').value = product.price;
    document.getElementById('edit-product-description').value = product.description || '';

    // Store the product ID for the form handler
    document.getElementById('edit-product-form').dataset.productId = id;
    openModal('edit-product-modal');
}

async function handleEditProduct(event) {
    event.preventDefault();

    const productId = event.target.dataset.productId;
    const updatedData = {
        name: document.getElementById('edit-product-name').value,
        price: parseFloat(document.getElementById('edit-product-price').value),
        description: document.getElementById('edit-product-description').value
    };

    try {
        await apiRequest(`/api/products/${productId}`, {
            method: 'PUT',
            body: JSON.stringify(updatedData)
        });

        showSuccess('Product updated successfully!');
        closeModal('edit-product-modal');
        event.target.reset();
        products = []; // Reset cache
        loadProducts();
        loadDashboardData();
    } catch (error) {
        showError('Failed to update product');
    }
}

// Delete Product Functions
function deleteProduct(id) {
    deleteConfirmData.type = 'product';
    deleteConfirmData.id = id;
    const product = products.find(p => p.product_id === id);
    document.getElementById('delete-confirmation-message').textContent = 
        `Are you sure you want to delete the product "${product.name}"? This action cannot be undone.`;
    openModal('delete-confirmation-modal');
}

async function importProductsCsv(event) {
    const file = event.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch(`${API_BASE}/api/products/import-csv`, {
            method: 'POST',
            headers: accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {},
            body: formData
        });
        if (!res.ok) throw new Error('Import failed');
        showSuccess('Products imported');
        products = [];
        loadProducts();
        loadDashboardData();
    } catch (e) {
        showError('Failed to import products');
    } finally {
        event.target.value = '';
    }
}

async function deleteProductConfirmed(id) {
    try {
        await apiRequest(`/api/products/${id}`, {
            method: 'DELETE'
        });

        showSuccess('Product deleted successfully!');
        products = []; // Reset cache
        loadProducts();
        loadDashboardData();
    } catch (error) {
        showError('Failed to delete product');
    }
}

// Edit Warehouse Functions
async function editWarehouse(id) {
    const warehouse = warehouses.find(w => w.warehouse_id === id);
    if (!warehouse) {
        showError('Warehouse not found');
        return;
    }

    document.getElementById('edit-warehouse-location').value = (warehouse.name || warehouse.location);
    document.getElementById('edit-warehouse-form').dataset.warehouseId = id;
    openModal('edit-warehouse-modal');
}

async function handleEditWarehouse(event) {
    event.preventDefault();

    const warehouseId = event.target.dataset.warehouseId;
    const updatedData = {
        location: document.getElementById('edit-warehouse-location').value
    };

    try {
        await apiRequest(`/api/warehouses/${warehouseId}`, {
            method: 'PUT',
            body: JSON.stringify(updatedData)
        });

        showSuccess('Warehouse updated successfully!');
        closeModal('edit-warehouse-modal');
        event.target.reset();
        warehouses = []; // Reset cache
        loadWarehouses();
        loadDashboardData();
    } catch (error) {
        showError('Failed to update warehouse');
    }
}

// Delete Warehouse Functions
function deleteWarehouse(id) {
    deleteConfirmData.type = 'warehouse';
    deleteConfirmData.id = id;
    const warehouse = warehouses.find(w => w.warehouse_id === id);
    document.getElementById('delete-confirmation-message').textContent = 
        `Are you sure you want to delete the warehouse "${warehouse.name || warehouse.location}"? This action cannot be undone.`;
    openModal('delete-confirmation-modal');
}

async function deleteWarehouseConfirmed(id) {
    try {
        await apiRequest(`/api/warehouses/${id}`, {
            method: 'DELETE'
        });

        showSuccess('Warehouse deleted successfully!');
        warehouses = []; // Reset cache
        loadWarehouses();
        loadDashboardData();
    } catch (error) {
        showError('Failed to delete warehouse');
    }
}

// View Warehouse Inventory
async function viewWarehouseInventory(warehouseId) {
    try {
        const inventoryDiv = document.getElementById('warehouse-inventory-content');
        inventoryDiv.innerHTML = '<p>Loading warehouse inventory...</p>';

        // Get inventory for this specific warehouse
        const warehouseItems = inventory.filter(item => item.warehouse_id === warehouseId);
        const warehouse = warehouses.find(w => w.warehouse_id === warehouseId);

        if (warehouseItems.length === 0) {
            inventoryDiv.innerHTML = '<p>No items in this warehouse</p>';
            openModal('warehouse-inventory-modal');
            return;
        }

        let totalValue = 0;
        let totalItems = 0;

        const tableHTML = `
            <div class="warehouse-info">
                <h3>${warehouse ? (warehouse.name || warehouse.location) : `Warehouse ${warehouseId}`}</h3>
                <p>${warehouse ? (warehouse.name || warehouse.location) : 'Unknown Warehouse'}</p>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Product ID</th>
                        <th>Product Name</th>
                        <th>Quantity</th>
                        <th>Unit Price</th>
                        <th>Total Value</th>
                    </tr>
                </thead>
                <tbody>
                    ${warehouseItems.map(item => {
                        const product = products.find(p => p.product_id === item.product_id);
                        const itemValue = (product ? product.price : 0) * item.quantity;
                        totalValue += itemValue;
                        totalItems += item.quantity;
                        return `
                            <tr>
                                <td>${item.product_id}</td>
                                <td>${product ? product.name : 'Unknown Product'}</td>
                                <td>${item.quantity}</td>
                                <td>$${product ? product.price.toFixed(2) : '0.00'}</td>
                                <td>$${itemValue.toFixed(2)}</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
            <div class="inventory-summary" style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px;">
                <h4>Summary</h4>
                <p><strong>Total Items:</strong> ${totalItems}</p>
                <p><strong>Total Value:</strong> $${totalValue.toFixed(2)}</p>
            </div>
        `;

        inventoryDiv.innerHTML = tableHTML;
        openModal('warehouse-inventory-modal');
    } catch (error) {
        showError('Failed to load warehouse inventory');
    }
}

// View Document Functions
async function loadDocumentDetails(documentId, silent = false) {
    try {
        const detailsDiv = document.getElementById('document-details-content');
        if (detailsDiv) detailsDiv.innerHTML = '<p>Loading document details...</p>';

        let document_data;
        try {
            document_data = await apiRequest(`/api/documents/${documentId}`);
        } catch (error) {
            if (!silent) showError('Document not found');
            return;
        }

        if (!document_data) {
            if (!silent) showError('Document not found');
            return;
        }

        // Get items for this document
        const items = document_data.items || [];
        let totalValue = 0;

        const itemsHTML = items.map(item => {
            const product = products.find(p => p.product_id === item.product_id);
            const itemValue = item.unit_price * item.quantity;
            totalValue += itemValue;
            return `
                <tr>
                    <td>${item.product_id}</td>
                    <td>${product ? product.name : 'Unknown Product'}</td>
                    <td>${item.quantity}</td>
                    <td>$${item.unit_price.toFixed(2)}</td>
                    <td>$${itemValue.toFixed(2)}</td>
                </tr>
            `;
        }).join('');

        const sourceWH = warehouses.find(w => w.warehouse_id === document_data.source_warehouse_id);
        const destWH = warehouses.find(w => w.warehouse_id === document_data.destination_warehouse_id);

        let warehouseInfo = '';
        if (document_data.doc_type === 'import') {
            warehouseInfo = `<p><strong>Destination Warehouse:</strong> ${destWH ? `${destWH.warehouse_id} - ${destWH.location}` : 'Unknown'}</p>`;
        } else if (document_data.doc_type === 'export') {
            warehouseInfo = `<p><strong>Source Warehouse:</strong> ${sourceWH ? `${sourceWH.warehouse_id} - ${sourceWH.location}` : 'Unknown'}</p>`;
        } else if (document_data.doc_type === 'transfer') {
            warehouseInfo = `
                <p><strong>Source Warehouse:</strong> ${sourceWH ? `${sourceWH.warehouse_id} - ${sourceWH.location}` : 'Unknown'}</p>
                <p><strong>Destination Warehouse:</strong> ${destWH ? `${destWH.warehouse_id} - ${destWH.location}` : 'Unknown'}</p>
            `;
        }

        const detailsHTML = `
            <div class="document-header">
                <div>
                    <h3>Document #${document_data.document_id}</h3>
                    <p><strong>Type:</strong> ${document_data.doc_type.toUpperCase()}</p>
                    <p><strong>Status:</strong> <span class="status-badge" style="background: ${document_data.status === 'posted' ? '#28a745' : '#ffc107'};">${document_data.status.toUpperCase()}</span></p>
                    <p><strong>Created:</strong> ${new Date(document_data.created_at).toLocaleString()}</p>
                    ${warehouseInfo}
                </div>
            </div>
            <h4 style="margin-top: 20px;">Items</h4>
            <table>
                <thead>
                    <tr>
                        <th>Product ID</th>
                        <th>Product Name</th>
                        <th>Quantity</th>
                        <th>Unit Price</th>
                        <th>Total Value</th>
                    </tr>
                </thead>
                <tbody>
                    ${itemsHTML}
                </tbody>
            </table>
            <div class="document-summary" style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px;">
                <h4>Summary</h4>
                <p><strong>Total Items:</strong> ${items.reduce((sum, item) => sum + item.quantity, 0)}</p>
                <p><strong>Total Value:</strong> $${totalValue.toFixed(2)}</p>
            </div>
        `;

        if (detailsDiv) detailsDiv.innerHTML = detailsHTML;
    } catch (error) {
        if (!silent) showError('Failed to load document details');
    }
}

async function viewDocument(documentId) {
    selectedDocumentId = documentId;
    clearInterval(documentAutoRefreshHandle);
    await loadDocumentDetails(documentId);
    openModal('view-document-modal');

    documentAutoRefreshHandle = setInterval(() => {
        if (!document.getElementById('view-document-modal')) {
            clearInterval(documentAutoRefreshHandle);
            documentAutoRefreshHandle = null;
            return;
        }
        const modal = document.getElementById('view-document-modal');
        if (!modal || modal.style.display === 'none' || modal.style.visibility === 'hidden') {
            clearInterval(documentAutoRefreshHandle);
            documentAutoRefreshHandle = null;
            return;
        }
        loadDocumentDetails(documentId, true);
    }, 15000);
}

// Post Document
async function postDocument(id) {
    try {
        if (!currentUser || !currentUser.email) {
            showError('Unable to post document: user not logged in');
            return;
        }
        
        await apiRequest(`/api/documents/${id}/post`, { 
            method: 'POST',
            body: JSON.stringify({ approved_by: currentUser.email })
        });
        showSuccess('Document posted successfully!');
        documents = []; // Reset cache
        loadDocuments();
        loadDashboardData();
    } catch (error) {
        console.error('Post document error:', error);
        showError(error.detail || 'Failed to post document');
    }
}

async function deleteDocument(id) {
    deleteConfirmData.type = 'document';
    deleteConfirmData.id = id;
    const doc = documents.find(d => d.document_id === id);
    document.getElementById('delete-confirmation-message').textContent = 
        `Are you sure you want to delete Document #${id}? This action cannot be undone.`;
    openModal('delete-confirmation-modal');
}

async function deleteDocumentConfirmed(id) {
    try {
        await apiRequest(`/api/documents/${id}`, {
            method: 'DELETE'
        });

        showSuccess('Document deleted successfully!');
        documents = []; // Reset cache
        loadDocuments();
        loadDashboardData();
    } catch (error) {
        console.error('Delete document error:', error);
        showError(error.detail || 'Failed to delete document');
    }
}

function toggleRealtime(enabled) {
    const settingsStatus = document.getElementById('settings-status');
    localStorage.setItem('realtime_updates', enabled ? 'true' : 'false');
    if (realtimeHandle) {
        clearInterval(realtimeHandle);
        realtimeHandle = null;
    }
    if (enabled) {
        realtimeHandle = setInterval(() => {
            loadDashboardData();
            loadDocuments();
            loadCustomers();
            loadInventory();
        }, 15000);
        if (settingsStatus) settingsStatus.textContent = 'Realtime updates ON';
    } else {
        if (settingsStatus) settingsStatus.textContent = 'Realtime updates OFF';
    }
}

// Confirm delete function
function confirmDelete() {
    if (deleteConfirmData.type === 'product') {
        deleteProductConfirmed(deleteConfirmData.id);
    } else if (deleteConfirmData.type === 'document') {
        deleteDocumentConfirmed(deleteConfirmData.id);
    } else if (deleteConfirmData.type === 'warehouse') {
        deleteWarehouseConfirmed(deleteConfirmData.id);
    }
    closeModal('delete-confirmation-modal');
}

// Setup event listeners for edit forms
// Note: Moved to main DOMContentLoaded listener to avoid duplicates


// --- AI Chat (LangChain) ---
function appendAiMessage(kind, text) {
    const log = document.getElementById('ai-chat-log');
    if (!log) return;
    const div = document.createElement('div');
    div.className = `ai-msg ai-msg--${kind}`;
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function clearAiChat() {
    const log = document.getElementById('ai-chat-log');
    if (log) {
        log.innerHTML = '<div class="ai-msg ai-msg--system">Ask questions about products, inventory, documents, customers… (read-only). Tip: press Ctrl+Enter to send.</div>';
    }
    const sql = document.getElementById('ai-sql');
    const rows = document.getElementById('ai-rows');
    if (sql) sql.textContent = '';
    if (rows) rows.textContent = '';
}

async function sendAiMessage() {
    const input = document.getElementById('ai-message');
    const btn = document.getElementById('ai-send-btn');
    const includeRows = document.getElementById('ai-include-rows');

    if (!input) return;
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    appendAiMessage('user', message);

    if (btn) btn.disabled = true;

    try {
        const payload = {
            message,
            include_rows: Boolean(includeRows && includeRows.checked),
        };

        const res = await apiRequest('/api/ai/chat-db', {
            method: 'POST',
            body: JSON.stringify(payload),
        });

        // apiRequest returns parsed json for 2xx
        appendAiMessage('assistant', res.answer || '(no answer)');

        const sqlEl = document.getElementById('ai-sql');
        const rowsEl = document.getElementById('ai-rows');
        if (sqlEl) sqlEl.textContent = res.sql || '';
        if (rowsEl) rowsEl.textContent = res.rows ? JSON.stringify(res.rows, null, 2) : '';
    } catch (e) {
        appendAiMessage('assistant', `Error: ${e && e.message ? e.message : String(e)}`);
    } finally {
        if (btn) btn.disabled = false;
    }
}
