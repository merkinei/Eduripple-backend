// Ripple Sound Effect Generator using Web Audio API
class RippleSound {
    constructor() {
        this.audioContext = null;
        this.initialized = false;
        this.init();
    }

    init() {
        if (typeof window !== 'undefined' && !this.initialized) {
            try {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                this.initialized = true;
            } catch (e) {
                console.warn('Web Audio API not available');
                this.initialized = false;
            }
        }
    }

    play() {
        if (!this.initialized || !this.audioContext) return;

        try {
            const now = this.audioContext.currentTime;
            
            // Create oscillators for ripple effect
            const osc1 = this.audioContext.createOscillator();
            const osc2 = this.audioContext.createOscillator();
            const osc3 = this.audioContext.createOscillator();
            const gain1 = this.audioContext.createGain();
            const gain2 = this.audioContext.createGain();
            const gain3 = this.audioContext.createGain();
            const masterGain = this.audioContext.createGain();
            const reverb = this.audioContext.createConvolver();

            // Set up oscillators for harmonic ripple
            osc1.frequency.setValueAtTime(800, now);
            osc2.frequency.setValueAtTime(600, now);
            osc3.frequency.setValueAtTime(400, now);

            // Frequency sweep for ripple effect
            osc1.frequency.exponentialRampToValueAtTime(1200, now + 0.1);
            osc2.frequency.exponentialRampToValueAtTime(900, now + 0.12);
            osc3.frequency.exponentialRampToValueAtTime(600, now + 0.15);

            // Set up gain envelopes
            gain1.gain.setValueAtTime(0.15, now);
            gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.15);

            gain2.gain.setValueAtTime(0.12, now);
            gain2.gain.exponentialRampToValueAtTime(0.01, now + 0.18);

            gain3.gain.setValueAtTime(0.1, now);
            gain3.gain.exponentialRampToValueAtTime(0.01, now + 0.2);

            masterGain.gain.setValueAtTime(0.3, now);
            masterGain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);

            // Connect nodes
            osc1.connect(gain1);
            osc2.connect(gain2);
            osc3.connect(gain3);
            gain1.connect(masterGain);
            gain2.connect(masterGain);
            gain3.connect(masterGain);
            masterGain.connect(this.audioContext.destination);

            // Play oscillators
            osc1.start(now);
            osc2.start(now);
            osc3.start(now);

            // Stop oscillators
            osc1.stop(now + 0.25);
            osc2.stop(now + 0.28);
            osc3.stop(now + 0.3);

        } catch (e) {
            console.error('Error playing ripple sound:', e);
        }
    }
}

// Create global ripple sound instance
const rippleSound = new RippleSound();

// Add ripple effect to AI generate buttons
document.addEventListener('DOMContentLoaded', function() {
    const generateButtons = document.querySelectorAll('[data-ripple-sound]');
    generateButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            rippleSound.play();
        });
    });

    // Also add to any button with class 'generate-resource'
    const resourceButtons = document.querySelectorAll('.generate-resource, .btn-primary[href*="ai_chat"], [href*="ai_chat"]');
    resourceButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            rippleSound.play();
        });
    });
});
