/**
 * 协议弹窗组件
 * 用于显示用户协议和投稿协议，支持强制阅读时间和同意确认
 */

class AgreementModal {
    constructor() {
        this.modal = null;
        this.readTime = 0;
        this.requiredReadTime = 5; // 强制阅读5秒
        this.timer = null;
        this.onAgree = null;
        this.onCancel = null;
    }

    /**
     * 显示协议弹窗
     * @param {string} agreementType - 协议类型 ('registration' 或 'submission')
     * @param {function} onAgree - 同意回调函数
     * @param {function} onCancel - 取消回调函数
     */
    show(agreementType, onAgree = null, onCancel = null) {
        this.onAgree = onAgree;
        this.onCancel = onCancel;
        this.readTime = 0;
        
        // 获取协议内容
        fetch(`/api/agreement/${agreementType}`)
            .then(response => response.json())
            .then(data => {
                if (data.content) {
                    this.createModal(data.content, agreementType);
                    this.startTimer();
                } else {
                    alert('获取协议内容失败');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('获取协议内容失败');
            });
    }

    /**
     * 创建弹窗HTML
     */
    createModal(content, agreementType) {
        const title = agreementType === 'registration' ? '用户注册协议' : '作品投稿协议';
        
        const modalHTML = `
            <div id="agreementModal" class="agreement-modal-overlay">
                <div class="agreement-modal">
                    <div class="agreement-modal-header">
                        <h4><i class="bi bi-file-text me-2"></i>${title}</h4>
                        <button type="button" class="agreement-close" onclick="agreementModal.close(false)">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                    <div class="agreement-modal-body">
                        <div class="agreement-content">
                            ${content}
                        </div>
                    </div>
                    <div class="agreement-modal-footer">
                        <div class="agreement-timer">
                            <i class="bi bi-clock me-1"></i>
                            <span>请仔细阅读协议内容，还需阅读 <span id="timerCount">${this.requiredReadTime}</span> 秒</span>
                        </div>
                        <div class="agreement-actions">
                            <div class="form-check mb-3" id="agreeCheckContainer" style="display: none;">
                                <input class="form-check-input" type="checkbox" id="agreeCheck">
                                <label class="form-check-label" for="agreeCheck">
                                    我已仔细阅读并同意以上协议
                                </label>
                            </div>
                            <div class="d-flex gap-2">
                                <button type="button" class="btn btn-secondary" onclick="agreementModal.close(false)">
                                    <i class="bi bi-x-circle me-1"></i>取消
                                </button>
                                <button type="button" class="btn btn-primary" id="agreeBtn" disabled onclick="agreementModal.close(true)">
                                    <i class="bi bi-check-circle me-1"></i>同意并继续
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 移除已存在的弹窗
        const existingModal = document.getElementById('agreementModal');
        if (existingModal) {
            existingModal.remove();
        }

        // 添加弹窗到页面
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('agreementModal');

        // 添加样式
        this.addStyles();

        // 显示弹窗
        setTimeout(() => {
            this.modal.classList.add('show');
        }, 100);

        // 绑定复选框事件
        const agreeCheck = document.getElementById('agreeCheck');
        const agreeBtn = document.getElementById('agreeBtn');
        
        agreeCheck.addEventListener('change', () => {
            agreeBtn.disabled = !agreeCheck.checked;
        });
    }

    /**
     * 添加样式
     */
    addStyles() {
        const styles = `
            <style id="agreementModalStyles">
                .agreement-modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(24, 24, 24, 0.9);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    z-index: 9999;
                    opacity: 0;
                    transition: opacity 0.3s ease;
                }
                
                .agreement-modal-overlay.show {
                    opacity: 1;
                }
                
                .agreement-modal {
                    background: #222;
                    color: #fff;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                    width: 90%;
                    max-width: 800px;
                    max-height: 90vh;
                    display: flex;
                    flex-direction: column;
                    transform: translateY(-50px);
                    transition: transform 0.3s ease;
                    border: 1px solid #444;
                }
                
                .agreement-modal-overlay.show .agreement-modal {
                    transform: translateY(0);
                }
                
                .agreement-modal-header {
                    padding: 20px 25px;
                    background: #333;
                    color: #fff;
                    border-radius: 12px 12px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid #444;
                }
                
                .agreement-modal-header h4 {
                    margin: 0;
                    font-weight: 600;
                    color: #fff;
                }
                
                .agreement-close {
                    background: none;
                    border: none;
                    color: #ccc;
                    font-size: 1.2rem;
                    cursor: pointer;
                    padding: 5px;
                    border-radius: 5px;
                    transition: all 0.3s ease;
                }
                
                .agreement-close:hover {
                    background: #555;
                    color: #fff;
                }
                
                .agreement-modal-body {
                    padding: 0;
                    overflow: hidden;
                    flex: 1;
                    display: flex;
                    flex-direction: column;
                }
                
                .agreement-content {
                    padding: 25px;
                    overflow-y: auto;
                    flex: 1;
                    max-height: 50vh;
                    line-height: 1.6;
                    font-size: 14px;
                    background: #222;
                    color: #ccc;
                }
                
                .agreement-content h1, .agreement-content h2, .agreement-content h3 {
                    color: #fff;
                    margin-top: 20px;
                    margin-bottom: 10px;
                }
                
                .agreement-content h3 {
                    color: #007bff;
                    font-size: 1.2rem;
                }
                
                .agreement-content h4 {
                    color: #ddd;
                    font-size: 1.1rem;
                    margin-top: 15px;
                    margin-bottom: 8px;
                }
                
                .agreement-content p {
                    margin-bottom: 15px;
                    color: #ccc;
                }
                
                .agreement-content ul, .agreement-content ol {
                    margin-bottom: 15px;
                    padding-left: 20px;
                }
                
                .agreement-content li {
                    margin-bottom: 8px;
                    color: #ccc;
                }
                
                .agreement-content strong {
                    color: #fff;
                }
                
                .agreement-modal-footer {
                    padding: 20px 25px;
                    border-top: 1px solid #444;
                    background: #333;
                    border-radius: 0 0 12px 12px;
                }
                
                .agreement-timer {
                    text-align: center;
                    margin-bottom: 15px;
                    color: #007bff;
                    font-weight: 500;
                }
                
                .agreement-timer i {
                    animation: pulse 2s infinite;
                }
                
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.5; }
                    100% { opacity: 1; }
                }
                
                .agreement-actions {
                    text-align: center;
                }
                
                .form-check {
                    text-align: left;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    color: #ccc;
                }
                
                .form-check-input {
                    margin-right: 8px;
                    accent-color: #007bff;
                }
                
                .form-check-input:checked {
                    background-color: #007bff;
                    border-color: #007bff;
                }
                
                .form-check-label {
                    color: #ccc;
                }
                
                .btn {
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: 500;
                    border: none;
                    transition: all 0.3s ease;
                    cursor: pointer;
                }
                
                .btn-primary {
                    background: #007bff;
                    color: white;
                }
                
                .btn-primary:hover:not(:disabled) {
                    background: #0056b3;
                    transform: translateY(-1px);
                }
                
                .btn-primary:disabled {
                    background: #555;
                    color: #888;
                    cursor: not-allowed;
                    transform: none;
                }
                
                .btn-secondary {
                    background: #555;
                    color: white;
                }
                
                .btn-secondary:hover {
                    background: #666;
                    transform: translateY(-1px);
                }
                
                .d-flex {
                    display: flex;
                }
                
                .gap-2 {
                    gap: 8px;
                }
                
                .mb-3 {
                    margin-bottom: 1rem;
                }
            </style>
        `;

        // 移除已存在的样式
        const existingStyles = document.getElementById('agreementModalStyles');
        if (existingStyles) {
            existingStyles.remove();
        }

        document.head.insertAdjacentHTML('beforeend', styles);
    }

    /**
     * 开始计时器
     */
    startTimer() {
        const timerCount = document.getElementById('timerCount');
        const agreeCheckContainer = document.getElementById('agreeCheckContainer');
        
        this.timer = setInterval(() => {
            this.readTime++;
            const remaining = this.requiredReadTime - this.readTime;
            
            if (remaining > 0) {
                timerCount.textContent = remaining;
            } else {
                // 阅读时间已满
                clearInterval(this.timer);
                timerCount.parentElement.innerHTML = '<i class="bi bi-check-circle me-1"></i>阅读时间已满，请勾选同意选项';
                agreeCheckContainer.style.display = 'block';
            }
        }, 1000);
    }

    /**
     * 关闭弹窗
     */
    close(agreed = false) {
        if (this.timer) {
            clearInterval(this.timer);
        }

        if (this.modal) {
            this.modal.classList.remove('show');
            
            setTimeout(() => {
                this.modal.remove();
                
                // 移除样式
                const styles = document.getElementById('agreementModalStyles');
                if (styles) {
                    styles.remove();
                }
                
                // 执行回调
                if (agreed && this.onAgree) {
                    this.onAgree();
                } else if (!agreed && this.onCancel) {
                    this.onCancel();
                }
            }, 300);
        }
    }
}

// 创建全局实例
const agreementModal = new AgreementModal();
