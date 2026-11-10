/**
 * ASET Anti-Cheating & Malpractice Prevention Engine
 * Supports Desktop, Laptop, Tablet, and Mobile Browsers
 */

class AntiCheatEngine {
    constructor(config) {
        this.sessionId = config.sessionId;
        this.maxStrikes = config.maxStrikes || 3;
        this.currentStrikes = config.currentStrikes || 0;
        this.studentInfo = config.studentInfo || { name: 'Student', roll: 'CS-000', ip: '127.0.0.1' };
        this.submitFormId = config.submitFormId || 'examSubmitForm';
        this.isExamActive = true;
        this.isSubmitting = false;

        this.init();
    }

    init() {
        this.setupSecurityEventListeners();
        this.setupShortcutsBlocker();
        this.setupWatermark();
        this.setupFullscreenEnforcement();
        this.updateStrikeDisplay();
    }

    setupSecurityEventListeners() {
        // Prevent Right Click
        document.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.handleViolation('Right Click Blocked', 'Attempted to open context menu.');
            return false;
        });

        // Prevent Text Selection & Copy
        document.addEventListener('selectstart', (e) => e.preventDefault());
        document.addEventListener('copy', (e) => {
            e.preventDefault();
            this.handleViolation('Copy Blocked', 'Attempted to copy exam content.');
        });
        document.addEventListener('cut', (e) => e.preventDefault());
        document.addEventListener('paste', (e) => e.preventDefault());

        // Prevent Dragging
        document.addEventListener('dragstart', (e) => e.preventDefault());

        // Detect Window / Tab / App Switching (Works on Mobile and Desktop)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && this.isExamActive && !this.isSubmitting) {
                this.handleViolation('Tab Switch / App Backgrounded', 'Exam tab lost visibility.');
            }
        });

        window.addEventListener('blur', () => {
            if (this.isExamActive && !this.isSubmitting) {
                this.handleViolation('Window Blur / Multi-Tasking', 'Window lost focus or cursor moved out.');
            }
        });

        window.addEventListener('pagehide', () => {
            if (this.isExamActive && !this.isSubmitting) {
                this.handleViolation('Page Switched', 'Navigated away or switched application.');
            }
        });

        // Warn before reload / close
        window.addEventListener('beforeunload', (e) => {
            if (this.isExamActive && !this.isSubmitting) {
                e.preventDefault();
                e.returnValue = 'Leaving or reloading will result in an anti-cheat strike!';
            }
        });
    }

    setupShortcutsBlocker() {
        window.addEventListener('keydown', (e) => {
            // Block F12 (DevTools)
            if (e.key === 'F12' || e.keyCode === 123) {
                e.preventDefault();
                this.handleViolation('DevTools Blocked', 'Pressed F12 inspect shortcut.');
                return false;
            }

            // Block Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C (DevTools)
            if (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'i' || e.key === 'J' || e.key === 'j' || e.key === 'C' || e.key === 'c')) {
                e.preventDefault();
                this.handleViolation('DevTools Blocked', 'Pressed Ctrl+Shift+I inspect shortcut.');
                return false;
            }

            // Block Ctrl+U (View Source)
            if (e.ctrlKey && (e.key === 'u' || e.key === 'U')) {
                e.preventDefault();
                this.handleViolation('Source Inspection Blocked', 'Pressed Ctrl+U shortcut.');
                return false;
            }

            // Block Ctrl+P (Print / PDF save)
            if (e.ctrlKey && (e.key === 'p' || e.key === 'P')) {
                e.preventDefault();
                this.handleViolation('Print Screen Blocked', 'Pressed Ctrl+P print shortcut.');
                return false;
            }

            // Block Ctrl+S (Save Page)
            if (e.ctrlKey && (e.key === 's' || e.key === 'S')) {
                e.preventDefault();
                return false;
            }

            // Block Alt+Tab detection (Alt key + Tab)
            if (e.altKey && (e.key === 'Tab' || e.keyCode === 9)) {
                e.preventDefault();
                this.handleViolation('Alt-Tab Switch', 'Attempted Alt+Tab application switch.');
                return false;
            }
        }, true);
    }

    setupFullscreenEnforcement() {
        const checkFullscreen = () => {
            const isFull = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
            if (!isFull && this.isExamActive && !this.isSubmitting) {
                const fsPrompt = document.getElementById('fullscreenPrompt');
                if (fsPrompt) {
                    fsPrompt.style.display = 'flex';
                }
            } else {
                const fsPrompt = document.getElementById('fullscreenPrompt');
                if (fsPrompt) fsPrompt.style.display = 'none';
            }
        };

        document.addEventListener('fullscreenchange', checkFullscreen);
        document.addEventListener('webkitfullscreenchange', checkFullscreen);
        document.addEventListener('mozfullscreenchange', checkFullscreen);
    }

    requestFullscreen() {
        const elem = document.documentElement;
        if (elem.requestFullscreen) {
            elem.requestFullscreen().catch(err => console.log('Fullscreen rejected:', err));
        } else if (elem.webkitRequestFullscreen) {
            elem.webkitRequestFullscreen();
        } else if (elem.msRequestFullscreen) {
            elem.msRequestFullscreen();
        }
        const fsPrompt = document.getElementById('fullscreenPrompt');
        if (fsPrompt) fsPrompt.style.display = 'none';
    }

    setupWatermark() {
        let watermark = document.getElementById('securityWatermark');
        if (!watermark) {
            watermark = document.createElement('div');
            watermark.id = 'securityWatermark';
            watermark.className = 'watermark-overlay';
            document.body.appendChild(watermark);
        }

        const renderWatermark = () => {
            const now = new Date().toLocaleTimeString();
            let itemsHtml = '';
            for (let i = 0; i < 12; i++) {
                itemsHtml += `<div class="watermark-item">
                    <span>${this.studentInfo.name} (${this.studentInfo.roll})</span>
                    <span style="font-size:0.75rem; color:#475569;">IP: ${this.studentInfo.ip} | ${now}</span>
                    <span style="font-size:0.7rem; color:#dc2626; font-weight: 800;">ASET SECURE PROCTOR</span>
                </div>`;
            }
            watermark.innerHTML = itemsHtml;
        };

        renderWatermark();
        setInterval(renderWatermark, 1000);
    }

    handleViolation(type, details) {
        if (!this.isExamActive || this.isSubmitting) return;

        this.currentStrikes++;
        this.updateStrikeDisplay();
        this.showWarningModal(type, details);

        fetch('/api/log-violation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: this.sessionId,
                type: type,
                details: details,
                strike_count: this.currentStrikes
            })
        }).catch(err => console.error('Violation logging failed:', err));

        if (this.currentStrikes >= this.maxStrikes) {
            this.triggerAutoSubmit('Maximum malpractice strikes exceeded! Exam terminated.');
        }
    }

    showWarningModal(type, details) {
        const modal = document.getElementById('cheatWarningModal');
        const titleElem = document.getElementById('warningType');
        const descElem = document.getElementById('warningDetails');
        const countElem = document.getElementById('warningCount');
        const maxElem = document.getElementById('warningMax');

        if (modal) {
            if (titleElem) titleElem.textContent = type;
            if (descElem) descElem.textContent = details;
            if (countElem) countElem.textContent = this.currentStrikes;
            if (maxElem) maxElem.textContent = this.maxStrikes;
            modal.style.display = 'flex';
        }
    }

    dismissWarning() {
        const modal = document.getElementById('cheatWarningModal');
        if (modal) modal.style.display = 'none';
        this.requestFullscreen();
    }

    updateStrikeDisplay() {
        const pills = document.querySelectorAll('.strike-pill');
        pills.forEach((pill, idx) => {
            if (idx < this.currentStrikes) {
                pill.classList.add('active');
            } else {
                pill.classList.remove('active');
            }
        });
    }

    triggerAutoSubmit(reason) {
        if (this.isSubmitting) return;
        this.isSubmitting = true;
        this.isExamActive = false;

        alert(reason || 'Exam auto-submitted due to malpractice violations.');
        const form = document.getElementById(this.submitFormId);
        if (form) {
            form.submit();
        } else {
            window.location.href = `/student/exam/${this.sessionId}/submit`;
        }
    }
}
