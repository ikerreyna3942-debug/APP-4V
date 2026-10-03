document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const dropzone = document.getElementById('dropzone');
    const imagePreview = document.getElementById('image-preview');
    const btnBorrar = document.getElementById('btn-borrar');
    const btnGenerar = document.getElementById('btn-generar');
    const loading = document.getElementById('loading');
    const resultArea = document.getElementById('result-area');
    const promptOutput = document.getElementById('prompt-output');
    const btnCopiar = document.getElementById('btn-copiar');

    const subVistas = document.getElementById('sub-vistas');
    const subEntorno = document.getElementById('sub-entorno');
    const mainButtonsContainer = document.getElementById('main-buttons-container');
    const gridSubVistas = document.getElementById('grid-sub-vistas');

    const inputMedidas = document.getElementById('input-medidas');
    const inputTipoMueble = document.getElementById('input-tipo-mueble');
    const inputLugarMueble = document.getElementById('input-lugar-mueble');

    let currentFile = null;

    // Ensure sub-options containers are hidden on initial load
    if (subVistas) subVistas.classList.add('hidden');
    if (subEntorno) subEntorno.classList.add('hidden');

    // Main Buttons Logic
    const vistasModes = ['vistas', 'vistas + tela y madera', 'vistas + tela'];

    if (mainButtonsContainer) {
        mainButtonsContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.main-btn');
            if (!btn) return;

            const botonVal = btn.dataset.boton || btn.innerText.trim();
            const isCurrentlyActive = btn.classList.contains('active');

            if (isCurrentlyActive) {
                // Clicking the active button again deselects it and hides sub-panels
                btn.classList.remove('active');
                if (subVistas) subVistas.classList.add('hidden');
                if (subEntorno) subEntorno.classList.add('hidden');
                return;
            }

            // Deselect any other main buttons
            document.querySelectorAll('.main-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Handle dynamic sub-panel visibility
            if (vistasModes.includes(botonVal)) {
                if (subVistas) subVistas.classList.remove('hidden');
                if (subEntorno) subEntorno.classList.add('hidden');
            } else if (botonVal === 'entorno') {
                if (subEntorno) subEntorno.classList.remove('hidden');
                if (subVistas) subVistas.classList.add('hidden');
            } else {
                // Any other main button hides both sub-panels
                if (subVistas) subVistas.classList.add('hidden');
                if (subEntorno) subEntorno.classList.add('hidden');
            }
        });
    }

    // Sub-options Chips (Vistas) Selection Logic
    if (gridSubVistas) {
        gridSubVistas.addEventListener('click', (e) => {
            const chip = e.target.closest('.sub-option-chip');
            if (!chip) return;

            gridSubVistas.querySelectorAll('.sub-option-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
        });
    }

    // Drag & Drop strict logic
    if (dropzone) {
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');

            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                const file = e.dataTransfer.files[0];
                if (file.type.startsWith('image/')) {
                    currentFile = file;
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                        imagePreview.src = ev.target.result;
                        imagePreview.classList.remove('hidden');
                        btnBorrar.disabled = false;
                        btnGenerar.disabled = false;
                    };
                    reader.readAsDataURL(file);
                } else {
                    alert('Por favor arrastra solo archivos de imagen.');
                }
            }
        });
    }

    // Absolute Reset Button
    if (btnBorrar) {
        btnBorrar.addEventListener('click', () => {
            currentFile = null;
            if (imagePreview) {
                imagePreview.src = '';
                imagePreview.classList.add('hidden');
            }
            btnBorrar.disabled = true;
            btnGenerar.disabled = true;

            if (resultArea) resultArea.classList.add('hidden');
            if (loading) loading.classList.add('hidden');
            if (promptOutput) promptOutput.value = '';

            // Reset all main buttons
            document.querySelectorAll('.main-btn').forEach(b => b.classList.remove('active'));

            // Hide sub-panels
            if (subVistas) subVistas.classList.add('hidden');
            if (subEntorno) subEntorno.classList.add('hidden');

            // Reset sub-options in Vistas to default
            if (gridSubVistas) {
                const chips = gridSubVistas.querySelectorAll('.sub-option-chip');
                chips.forEach(c => c.classList.remove('active'));
                const defaultChip = gridSubVistas.querySelector('.sub-option-chip[data-sub="Frontal 0°"]') || chips[0];
                if (defaultChip) defaultChip.classList.add('active');
            }

            // Clear inputs in Entorno
            if (inputMedidas) inputMedidas.value = '';
            if (inputTipoMueble) inputTipoMueble.value = '';
            if (inputLugarMueble) inputLugarMueble.value = '';
        });
    }

    // Generate Prompt API Call
    if (btnGenerar) {
        btnGenerar.addEventListener('click', async () => {
            if (!currentFile) {
                alert('Por favor carga una imagen primero.');
                return;
            }

            // Collect active main button
            const activeMainBtn = document.querySelector('.main-btn.active');
            const botonPrincipal = activeMainBtn ? (activeMainBtn.dataset.boton || activeMainBtn.innerText.trim()) : '';

            // Collect sub_opcion if vistas mode selected
            let subOpcion = '';
            if (vistasModes.includes(botonPrincipal)) {
                const activeSubChip = document.querySelector('#grid-sub-vistas .sub-option-chip.active');
                subOpcion = activeSubChip ? (activeSubChip.dataset.sub || activeSubChip.innerText.trim()) : 'Frontal 0°';
            }

            // Collect entorno fields if entorno mode selected
            let medidas = '';
            let tipoMueble = '';
            let lugarMueble = '';
            if (botonPrincipal === 'entorno') {
                if (inputMedidas) medidas = inputMedidas.value.trim();
                if (inputTipoMueble) tipoMueble = inputTipoMueble.value.trim();
                if (inputLugarMueble) lugarMueble = inputLugarMueble.value.trim();
            }

            const formData = new FormData();
            formData.append('image', currentFile);
            formData.append('boton_principal', botonPrincipal);
            formData.append('sub_opcion', subOpcion);
            formData.append('medidas', medidas);
            formData.append('tipo_mueble', tipoMueble);
            formData.append('lugar_mueble', lugarMueble);

            // Backward compatibility fields
            formData.append('vista', subOpcion || botonPrincipal || 'Frontal');
            formData.append('tela', '');
            formData.append('madera', '');
            formData.append('ambiente', '');

            btnGenerar.disabled = true;
            if (loading) loading.classList.remove('hidden');
            if (resultArea) resultArea.classList.add('hidden');

            try {
                const res = await fetch('/api/generate', {
                    method: 'POST',
                    body: formData
                });

                const data = await res.json();

                if (data.success) {
                    if (promptOutput) promptOutput.value = data.prompt;
                    if (resultArea) resultArea.classList.remove('hidden');
                } else {
                    alert('Error: ' + (data.error || 'No se pudo generar el prompt.'));
                }
            } catch (err) {
                alert('Error de conexión al servidor.');
            } finally {
                btnGenerar.disabled = false;
                if (loading) loading.classList.add('hidden');
            }
        });
    }

    // Copy Prompt Button
    if (btnCopiar) {
        btnCopiar.addEventListener('click', () => {
            if (!promptOutput || !promptOutput.value) return;

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(promptOutput.value);
            } else {
                promptOutput.select();
                document.execCommand('copy');
            }

            const originalText = btnCopiar.innerText;
            btnCopiar.innerText = '¡Copiado!';
            setTimeout(() => {
                btnCopiar.innerText = originalText;
            }, 2000);
        });
    }
});
