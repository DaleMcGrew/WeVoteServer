// Saved Audiences Drawer JavaScript

// Store event handlers so we can remove them later
let currentMouseMoveHandler = null;
let currentMouseUpHandler = null;

// Initialize resize functionality
function initializeResizeHandle() {
    const resizeHandle = document.getElementById('resizeHandle');
    const previewSection = document.getElementById('previewSection');
    const drawerHeader = document.getElementById('drawerHeader');

    if (!resizeHandle || !previewSection || !drawerHeader) {
        console.warn('Saved Audiences Drawer: Required elements not found for resize');
        return;
    }

    let isResizing = false;
    let startY = 0;
    let startHeight = 0;

    // Calculate the maximum height (stop right below the title row with buttons)
    function getMaxHeight() {
        const drawer = document.getElementById('savedAudiencesDrawer');
        const drawerHeight = drawer.offsetHeight;

        // Find the title row to measure where it ends
        const titleRow = drawerHeader.querySelector('.drawer-title-row');
        if (titleRow) {
            const titleRowBottom = titleRow.getBoundingClientRect().bottom - drawer.getBoundingClientRect().top;
            // Max height = drawer height - title row bottom position - small margin
            return drawerHeight - titleRowBottom - 10;
        }

        // Fallback: use approximate title row height
        return drawerHeight - 80;
    }

    // Remove previous event listeners if they exist
    if (currentMouseMoveHandler) {
        document.removeEventListener('mousemove', currentMouseMoveHandler);
    }
    if (currentMouseUpHandler) {
        document.removeEventListener('mouseup', currentMouseUpHandler);
    }

    // Clone and replace the resize handle to remove all its event listeners
    const newResizeHandle = resizeHandle.cloneNode(true);
    resizeHandle.parentNode.replaceChild(newResizeHandle, resizeHandle);

    // Mouse down on resize handle
    newResizeHandle.addEventListener('mousedown', function(e) {
        isResizing = true;
        startY = e.clientY;
        startHeight = previewSection.offsetHeight;

        e.preventDefault();
        newResizeHandle.classList.add('resizing');
        document.body.style.cursor = 'ns-resize';
        document.body.style.userSelect = 'none';
    });

    // Mouse move - resize preview section
    const mouseMoveHandler = function(e) {
        if (!isResizing) return;

        // Calculate new height (inverted because section grows upward)
        const deltaY = startY - e.clientY;
        const newHeight = startHeight + deltaY;

        // Get constraints
        const minHeight = 60;  // Minimum collapsed height
        const maxHeight = getMaxHeight();  // Maximum height (right below header)

        // Constrain the height
        const constrainedHeight = Math.max(minHeight, Math.min(newHeight, maxHeight));

        // Apply the new height
        previewSection.style.height = constrainedHeight + 'px';
    };

    // Mouse up - stop resizing
    const mouseUpHandler = function() {
        if (isResizing) {
            isResizing = false;
            newResizeHandle.classList.remove('resizing');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    };

    document.addEventListener('mousemove', mouseMoveHandler);
    document.addEventListener('mouseup', mouseUpHandler);
}

// Open the drawer
function openSavedAudiencesDrawer(audienceBuilderId = '') {
    // console.log('openSavedAudiencesDrawer audience builder ID:', audienceBuilderId);
    const audienceBuilderIdContent = document.getElementById('audience_builder_id_id');
    const audienceBuilderNameContent = document.getElementById('audience_builder_name_id');
    const drawer = document.getElementById('savedAudiencesDrawer');
    const drawerContent = document.getElementById('audienceBuilderDrawerHTML');
    const overlay = document.getElementById('savedAudiencesOverlay');

    if (drawer && overlay) {
        drawer.classList.add('open');
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Initialize resize handle after drawer is opened
        setTimeout(() => {
            initializeResizeHandle();
        }, 100);
    }
    if (drawerContent) {
        // Show loading state
        drawerContent.innerHTML = '<div class="loading-spinner">Loading audience builder...</div>';
        audienceBuilderIdContent.value = audienceBuilderId;
        audienceBuilderNameContent.value = 'Loading...';

        // Fetch the HTML from the server
        const url = '/email/audience_builder_drawer_html' + '?audience_builder_id=' + audienceBuilderId;

        fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json',
            },
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                drawerContent.innerHTML = data.html;
                audienceBuilderNameContent.value = data.audience_builder_name;
            } else {
                drawerContent.innerHTML = '<div class="error-message">Error loading content: ' + data.status + '</div>';
            }
            initializeResizeHandle();
        })
        .catch(error => {
            console.error('Error fetching audience builder HTML:', error);
            drawerContent.innerHTML = '<div class="error-message">Failed to load audience builder. Please try again.</div>';
        });
    }
}

// Close the drawer
function closeSavedAudiencesDrawer() {
    const drawer = document.getElementById('savedAudiencesDrawer');
    const overlay = document.getElementById('savedAudiencesOverlay');

    if (drawer && overlay) {
        drawer.classList.remove('open');
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Handle form submission within the drawer
function setupDrawerFormSubmission() {
    const form = document.getElementById('audience-builder-form');
    if (form) {
        console.log('setupDrawerFormSubmission, form FOUND');
    } else {
        console.log('setupDrawerFormSubmission, form NOT found');
    }
    if (form) {
        form.addEventListener('submit', function(event) {
            event.preventDefault(); // Prevent default form submission

            const formData = new FormData(form);
            const drawerContent = document.getElementById('audienceBuilderDrawerHTML');

            // Show loading state
            if (drawerContent) {
                drawerContent.innerHTML = '<div class="loading-spinner">Saving and reloading...</div>';
            }

            // Submit form via fetch
            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Update the drawer content with the returned HTML
                    if (drawerContent && data.html) {
                        drawerContent.innerHTML = data.html;
                        initializeResizeHandle();
                    }

                    // Show success message if provided
                    if (data.message) {
                        showDrawerMessage(data.message, 'success');
                    }
                } else {
                    // Show error message
                    if (drawerContent) {
                        drawerContent.innerHTML = '<div class="error-message">Error: ' + (data.status || 'Unknown error') + '</div>';
                    }
                    if (data.message) {
                        showDrawerMessage(data.message, 'error');
                    }
                }
            })
            .catch(error => {
                console.error('Error submitting form:', error);
                if (drawerContent) {
                    drawerContent.innerHTML = '<div class="error-message">Failed to save. Please try again.</div>';
                }
                showDrawerMessage('Failed to save audience builder', 'error');
            });
        });
    }
}

// Helper function to show messages in the drawer
function showDrawerMessage(message, type) {
    const header = document.getElementById('drawerHeader');
    if (header) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `drawer-message drawer-message-${type}`;
        messageDiv.textContent = message;
        header.appendChild(messageDiv);

        // Remove message after 5 seconds
        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }
}

function submitAddDeleteButtonFromDrawer(buttonElement) {
    const form = document.getElementById('audience-builder-form');
    if (form) {
        const formData = new FormData(form);

        // Add the button's name and value to the form data
        const buttonName = buttonElement.getAttribute('data-name');
        const buttonValue = buttonElement.getAttribute('data-value');
        formData.append(buttonName, buttonValue);

        const drawerContent = document.getElementById('audienceBuilderDrawerHTML');

        // Show loading state
        if (drawerContent) {
            drawerContent.innerHTML = '<div class="loading-spinner">Saving and reloading...</div>';
        }

        // Submit form via fetch
        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Update the drawer content with the returned HTML
                if (drawerContent && data.html) {
                    drawerContent.innerHTML = data.html;
                    initializeResizeHandle();
                }

                // Show success message if provided
                if (data.message) {
                    showDrawerMessage(data.message, 'success');
                }
            } else {
                // Show error message
                if (drawerContent) {
                    drawerContent.innerHTML = '<div class="error-message">Error: ' + (data.status || 'Unknown error') + '</div>';
                }
                if (data.message) {
                    showDrawerMessage(data.message, 'error');
                }
            }
        })
        .catch(error => {
            console.error('Error submitting form:', error);
            if (drawerContent) {
                drawerContent.innerHTML = '<div class="error-message">Failed to save. Please try again.</div>';
            }
            showDrawerMessage('Failed to save audience builder', 'error');
        });
    }
}

// Initialize draggable functionality
document.addEventListener('DOMContentLoaded', function() {
    // Close drawer on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const drawer = document.getElementById('savedAudiencesDrawer');
            if (drawer && drawer.classList.contains('open')) {
                closeSavedAudiencesDrawer();
            }
        }
    });
});

// Expose functions globally
window.openSavedAudiencesDrawer = openSavedAudiencesDrawer;
window.closeSavedAudiencesDrawer = closeSavedAudiencesDrawer;
window.submitAddDeleteButtonFromDrawer = submitAddDeleteButtonFromDrawer;
