// Saved Audiences Drawer JavaScript

// Open the drawer
function openSavedAudiencesDrawer() {
    const drawer = document.getElementById('savedAudiencesDrawer');
    const overlay = document.getElementById('savedAudiencesOverlay');

    if (drawer && overlay) {
        drawer.classList.add('open');
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
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

// Save audience (placeholder)
function saveSavedAudience() {
    console.log('Saving audience...');
    alert('Save functionality will be connected to backend in next ticket!');
}

// Initialize draggable functionality
document.addEventListener('DOMContentLoaded', function() {
    const resizeHandle = document.getElementById('resizeHandle');
    const previewSection = document.getElementById('previewSection');
    const drawerHeader = document.getElementById('drawerHeader');

    if (!resizeHandle || !previewSection || !drawerHeader) {
        console.warn('Saved Audiences Drawer: Required elements not found');
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

    // Mouse down on resize handle
    resizeHandle.addEventListener('mousedown', function(e) {
        isResizing = true;
        startY = e.clientY;
        startHeight = previewSection.offsetHeight;

        e.preventDefault();
        resizeHandle.classList.add('resizing');
        document.body.style.cursor = 'ns-resize';
        document.body.style.userSelect = 'none';
    });

    // Mouse move - resize preview section
    document.addEventListener('mousemove', function(e) {
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
    });

    // Mouse up - stop resizing
    document.addEventListener('mouseup', function() {
        if (isResizing) {
            isResizing = false;
            resizeHandle.classList.remove('resizing');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });

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
window.saveSavedAudience = saveSavedAudience;