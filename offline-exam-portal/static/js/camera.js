/**
 * WebRTC Camera & Facial Attendance Verification Engine for ASET
 * Cross-device support (Smartphone front-camera, Laptop webcam, USB camera)
 */

class ProctorCamera {
    constructor(videoElemId, canvasElemId) {
        this.video = document.getElementById(videoElemId);
        this.canvas = document.getElementById(canvasElemId) || document.createElement('canvas');
        this.stream = null;
    }

    async startCamera() {
        try {
            const constraints = {
                video: {
                    facingMode: 'user',
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                },
                audio: false
            };
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            if (this.video) {
                this.video.srcObject = this.stream;
                this.video.play();
            }
            return { success: true };
        } catch (err) {
            console.warn('Initial camera access failed, trying fallback constraints:', err);
            try {
                this.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                if (this.video) {
                    this.video.srcObject = this.stream;
                    this.video.play();
                }
                return { success: true };
            } catch (fallbackErr) {
                console.error('All camera attempts failed:', fallbackErr);
                return { success: false, error: fallbackErr.message };
            }
        }
    }

    captureSnapshot() {
        if (!this.video || !this.video.videoWidth) {
            return null;
        }
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        const ctx = this.canvas.getContext('2d');
        ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        return this.canvas.toDataURL('image/jpeg', 0.85);
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
    }
}
