// Guide Modal Functions
let currentStep = 1;
const totalSteps = 3;

function openGuide() {
    document.getElementById('guideModal').style.display = 'block';
    document.body.style.overflow = 'hidden'; // Prevent scrolling
}

function closeGuide() {
    document.getElementById('guideModal').style.display = 'none';
    document.body.style.overflow = 'auto'; // Restore scrolling
    goToStep(1); // Reset to first step
}

function startLearning() {
    closeGuide();
    window.location.href = 'https://www.oqyai.kz/lesson/1/';
}

function goToStep(step) {
    currentStep = step;

    // Hide all steps
    document.querySelectorAll('.guide-step').forEach(el => {
        el.classList.remove('active');
    });

    // Show current step
    document.querySelector(`.guide-step[data-step="${step}"]`).classList.add('active');

    // Update dots
    document.querySelectorAll('.guide-dot').forEach((dot, index) => {
        if (index + 1 === step) {
            dot.classList.add('active');
        } else {
            dot.classList.remove('active');
        }
    });

    // Update buttons
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const startBtn = document.getElementById('startBtn');

    if (step === 1) {
        prevBtn.style.visibility = 'hidden';
    } else {
        prevBtn.style.visibility = 'visible';
    }

    if (step === totalSteps) {
        nextBtn.style.display = 'none';
        startBtn.style.display = 'block';
    } else {
        nextBtn.style.display = 'block';
        startBtn.style.display = 'none';
    }
}

function nextStep() {
    if (currentStep < totalSteps) {
        goToStep(currentStep + 1);
    }
}

function previousStep() {
    if (currentStep > 1) {
        goToStep(currentStep - 1);
    }
}

// Event listener for guide button
document.addEventListener('DOMContentLoaded', function() {
    const guideBtn = document.getElementById('guide-btn');
    if (guideBtn) {
        guideBtn.addEventListener('click', openGuide);
    }

    // Close modal when clicking outside
    const guideModal = document.getElementById('guideModal');
    if (guideModal) {
        guideModal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeGuide();
            }
        });
    }

    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
        if (guideModal && guideModal.style.display === 'block') {
            if (e.key === 'ArrowRight') nextStep();
            if (e.key === 'ArrowLeft') previousStep();
            if (e.key === 'Escape') closeGuide();
        }
    });
});
