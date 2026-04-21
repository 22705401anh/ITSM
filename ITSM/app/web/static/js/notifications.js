/**
 * Professional Modal Notifications
 * Replaces browser alerts with beautiful modals
 */

class ProfessionalNotification {
    constructor() {
        this.createModalHTML();
    }

    createModalHTML() {
        // Check if already exists
        if (document.getElementById('professionalNotificationModal')) {
            return;
        }

        const html = `
            <div class="modal fade" id="professionalNotificationModal" tabindex="-1" data-bs-backdrop="static">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content border-0 shadow-lg">
                        <div class="modal-header border-0" id="notificationHeader">
                            <div class="d-flex align-items-center w-100">
                                <i class="fas fa-circle-notch me-3 fa-2x" id="notificationIcon"></i>
                                <h5 class="modal-title" id="notificationTitle">Notification</h5>
                            </div>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body" id="notificationBody">
                            <p id="notificationMessage">Message here</p>
                        </div>
                        <div class="modal-footer border-0 pt-0">
                            <button type="button" id="notificationBtn" class="btn btn-primary btn-lg px-5" data-bs-dismiss="modal">
                                <i class="fas fa-check me-2"></i> OK
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <style>
                #professionalNotificationModal .modal-content {
                    border-radius: 1rem;
                    overflow: hidden;
                }

                #professionalNotificationModal .modal-header {
                    padding: 2rem;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }

                #professionalNotificationModal .modal-header h5 {
                    color: white;
                    font-weight: 600;
                    margin: 0;
                }

                #professionalNotificationModal .modal-body {
                    padding: 2rem;
                    font-size: 1.1rem;
                    line-height: 1.6;
                    color: #333;
                }

                #professionalNotificationModal .modal-footer {
                    padding: 1.5rem 2rem;
                    background: #f8f9fa;
                }

                /* Success Style */
                #professionalNotificationModal.success .modal-header {
                    background: linear-gradient(135deg, #00b894 0%, #00a86b 100%);
                }

                #professionalNotificationModal.success #notificationIcon {
                    color: #00b894;
                    animation: successCheckmark 0.6s ease-in-out;
                }

                #professionalNotificationModal.success #notificationBtn {
                    background: #00b894;
                    border-color: #00b894;
                }

                #professionalNotificationModal.success #notificationBtn:hover {
                    background: #00a86b;
                    border-color: #00a86b;
                }

                /* Error Style */
                #professionalNotificationModal.error .modal-header {
                    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
                }

                #professionalNotificationModal.error #notificationIcon {
                    color: #ff6b6b;
                    animation: errorShake 0.5s ease-in-out;
                }

                #professionalNotificationModal.error #notificationBtn {
                    background: #ff6b6b;
                    border-color: #ff6b6b;
                }

                #professionalNotificationModal.error #notificationBtn:hover {
                    background: #ee5a6f;
                    border-color: #ee5a6f;
                }

                /* Warning Style */
                #professionalNotificationModal.warning .modal-header {
                    background: linear-gradient(135deg, #ffa502 0%, #ff8c00 100%);
                }

                #professionalNotificationModal.warning #notificationIcon {
                    color: #ffa502;
                    animation: warningPulse 1s ease-in-out infinite;
                }

                #professionalNotificationModal.warning #notificationBtn {
                    background: #ffa502;
                    border-color: #ffa502;
                }

                #professionalNotificationModal.warning #notificationBtn:hover {
                    background: #ff8c00;
                    border-color: #ff8c00;
                }

                /* Info Style */
                #professionalNotificationModal.info .modal-header {
                    background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
                }

                #professionalNotificationModal.info #notificationIcon {
                    color: #3498db;
                    animation: infoBounce 1s ease-in-out infinite;
                }

                #professionalNotificationModal.info #notificationBtn {
                    background: #3498db;
                    border-color: #3498db;
                }

                #professionalNotificationModal.info #notificationBtn:hover {
                    background: #2980b9;
                    border-color: #2980b9;
                }

                /* Animations */
                @keyframes successCheckmark {
                    0% {
                        transform: scale(0) rotate(0deg);
                    }
                    50% {
                        transform: scale(1.1) rotate(10deg);
                    }
                    100% {
                        transform: scale(1) rotate(0deg);
                    }
                }

                @keyframes errorShake {
                    0%, 100% { transform: translateX(0); }
                    25% { transform: translateX(-10px); }
                    75% { transform: translateX(10px); }
                }

                @keyframes warningPulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.7; }
                }

                @keyframes infoBounce {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-10px); }
                }

                #notificationIcon {
                    display: inline-block;
                    min-width: 2.5rem;
                }
            </style>
        `;

        // Create a container div and append to body
        const container = document.createElement('div');
        container.innerHTML = html;
        document.body.appendChild(container);
    }

    show(type = 'success', title = 'Success', message = 'Operation completed successfully!', callback = null) {
        // Ensure modal HTML exists
        this.createModalHTML();

        const modal = document.getElementById('professionalNotificationModal');
        const header = document.getElementById('notificationHeader');
        const icon = document.getElementById('notificationIcon');
        const titleEl = document.getElementById('notificationTitle');
        const messageEl = document.getElementById('notificationMessage');
        const btn = document.getElementById('notificationBtn');

        // Remove previous type classes
        modal.classList.remove('success', 'error', 'warning', 'info');
        modal.classList.add(type);

        // Set icon based on type
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        icon.className = `fa-2x me-3 ${icons[type] || icons.info}`;
        titleEl.textContent = title;
        messageEl.textContent = message;

        // Clear previous callback
        btn.onclick = null;

        // Show modal
        const bsModal = new bootstrap.Modal(modal, { backdrop: 'static', keyboard: false });

        // Add callback on close if provided
        if (callback) {
            modal.addEventListener('hidden.bs.modal', callback, { once: true });
        }

        bsModal.show();
    }

    success(title = 'Success!', message = 'Operation completed successfully!', callback = null) {
        this.show('success', title, message, callback);
    }

    error(title = 'Error!', message = 'Something went wrong. Please try again.', callback = null) {
        this.show('error', title, message, callback);
    }

    warning(title = 'Warning!', message = 'Please be careful with this action.', callback = null) {
        this.show('warning', title, message, callback);
    }

    info(title = 'Information', message = 'Here is some information.', callback = null) {
        this.show('info', title, message, callback);
    }
}

// Initialize globally
const Notification = new ProfessionalNotification();
