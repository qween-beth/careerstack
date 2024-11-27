// static/js/upload.js
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.querySelector('form');
    const alertContainer = document.createElement('div');
    alertContainer.className = 'fixed top-4 right-4 max-w-sm';
    document.body.appendChild(alertContainer);

    function showAlert(message, type) {
        const alert = document.createElement('div');
        alert.className = `${type} p-4 rounded-lg shadow-lg mb-4 transform transition-all duration-500 ease-in-out translate-x-0`;
        
        let bgColor;
        switch(type) {
            case 'success':
                bgColor = 'bg-green-50 text-green-800 border-l-4 border-green-400';
                break;
            case 'info':
                bgColor = 'bg-blue-50 text-blue-800 border-l-4 border-blue-400';
                break;
            case 'error':
                bgColor = 'bg-red-50 text-red-800 border-l-4 border-red-400';
                break;
        }
        alert.className += ` ${bgColor}`;

        alert.innerHTML = `
            <div class="flex">
                <div class="flex-shrink-0">
                    <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                    </svg>
                </div>
                <div class="ml-3">
                    <p class="text-sm">${message}</p>
                </div>
            </div>
        `;

        alertContainer.appendChild(alert);

        // Remove alert after 5 seconds
        setTimeout(() => {
            alert.classList.add('translate-x-full', 'opacity-0');
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    }

    // Handle file input change for drag and drop visual feedback
    const dropZone = document.querySelector('.border-dashed');
    const fileInput = document.querySelector('input[type="file"]');

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-indigo-500', 'bg-indigo-50');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
        fileInput.files = e.dataTransfer.files;
        // Update file name display if you want
    });

    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        showAlert('Uploading resume...', 'info');
        
        const formData = new FormData(this);
        
        try {
            const response = await fetch('/upload_resume', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                showAlert('Resume uploaded successfully! Analyzing resume...', 'success');
                
                // Poll for analysis completion
                const checkAnalysis = async () => {
                    const analysisResponse = await fetch('/check_analysis_status');
                    const analysisData = await analysisResponse.json();
                    
                    if (analysisData.success) {
                        showAlert('Analysis complete! Redirecting to chat...', 'success');
                        setTimeout(() => {
                            window.location.href = '/chat';
                        }, 1500);
                    } else if (!analysisData.error) {
                        // If still processing, check again in 1 second
                        setTimeout(checkAnalysis, 1000);
                    } else {
                        throw new Error(analysisData.error);
                    }
                };
                
                checkAnalysis();
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            showAlert(`Error: ${error.message}`, 'error');
        }
    });
});