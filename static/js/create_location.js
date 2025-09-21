// JS helper to create municipality and barangay via AJAX
// Requires Bootstrap 5 and jQuery (both are included in base.html)

(function(){
    function showToast(message, type='info'){
        // Create a transient toast using Bootstrap Toast component
        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
              <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
              </div>
            </div>
        `;
        const container = document.getElementById('toast-container');
        if (!container) return console.warn('Toast container not found');
        container.insertAdjacentHTML('beforeend', toastHtml);
        const el = document.getElementById(toastId);
        const bs = new bootstrap.Toast(el, {delay: 4000});
        bs.show();
        el.addEventListener('hidden.bs.toast', () => el.remove());
    }

    function handleCreateMunicipality(formEl, callback){
        const url = '/api/create-municipality/';
        const data = $(formEl).serialize();
        showToast('Creating municipality...', 'info');
        $.post(url, data)
            .done(function(res){
                if (res.success){
                    showToast(res.message || 'Municipality created', 'success');
                    // If we're currently on the Add Barangay page, focus the barangay form so user can continue
                    try {
                        const onAddBarangayPage = window.location.pathname.indexOf('/barangays/add') !== -1 || document.getElementById('submit-barangay');
                        if (onAddBarangayPage) {
                            // Close modal (templates may also close it themselves)
                            const modalEl = document.getElementById('createMunicipalityModal');
                            if (modalEl) {
                                const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                                modal.hide();
                            }
                            // Add option and select (some templates already do this in their callbacks)
                            const sel = document.getElementById('id_municipality');
                            if (sel && !Array.from(sel.options).some(o => o.value == res.id)) {
                                const opt = document.createElement('option');
                                opt.value = res.id;
                                opt.textContent = res.name;
                                sel.appendChild(opt);
                            }
                            if (sel) sel.value = res.id;
                            // Focus the barangay name input if exists
                            const barangayName = document.getElementById('id_name') || document.querySelector('input[name="name"]');
                            if (barangayName) barangayName.focus();
                            showToast('Municipality created — you can now add a barangay', 'info');
                        } else {
                            // If not on add-barangay page, redirect to add-barangay with municipality preselected
                            window.location.href = '/barangays/add/?municipality_id=' + encodeURIComponent(res.id);
                        }
                    } catch (e) {
                        console.debug('Post-create municipality flow failed', e);
                    }

                    if (typeof callback === 'function') callback(null, res);
                } else {
                    showToast(res.message || 'Failed to create municipality', 'danger');
                    if (typeof callback === 'function') callback(new Error(res.message || 'Failed'));
                }
            })
            .fail(function(xhr){
                let msg = 'Error creating municipality';
                try { msg = xhr.responseJSON.message || JSON.stringify(xhr.responseJSON.errors); } catch(e){}
                showToast(msg, 'danger');
                if (typeof callback === 'function') callback(new Error(msg));
            });
    }

    function handleCreateBarangay(formEl, callback){
        const url = '/api/create-barangay/';
        const data = $(formEl).serialize();
        // Prevent double-submit by using a data attribute on the form element
        if (formEl.dataset.submitting === 'true') {
            showToast('Submission already in progress...', 'warning');
            return;
        }
        formEl.dataset.submitting = 'true';
        // Disable submit button(s) inside the form if present
        const submitButtons = formEl.querySelectorAll('button[type="submit"], input[type="submit"]');
        submitButtons.forEach(b => b.disabled = true);

        showToast('Creating barangay...', 'info');
        $.post(url, data)
            .done(function(res){
                if (res.success){
                    showToast(res.message || 'Barangay created', 'success');
                    if (typeof callback === 'function') callback(null, res);
                } else {
                    showToast(res.message || 'Failed to create barangay', 'danger');
                    if (typeof callback === 'function') callback(new Error(res.message || 'Failed'));
                }
            })
            .fail(function(xhr){
                let msg = 'Error creating barangay';
                try { msg = xhr.responseJSON.message || JSON.stringify(xhr.responseJSON.errors); } catch(e){}
                showToast(msg, 'danger');
                if (typeof callback === 'function') callback(new Error(msg));
            })
            .always(function(){
                // Re-enable buttons and clear flag
                formEl.dataset.submitting = 'false';
                submitButtons.forEach(b => b.disabled = false);
            });
    }

    // Expose to global for inline use on templates
    window.createLocation = {
        createMunicipality: handleCreateMunicipality,
        createBarangay: handleCreateBarangay,
        showToast: showToast
    };
})();
