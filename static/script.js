document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------------------
    // DOM Element References
    // -------------------------------------------------------------------------
    // Zone 1: Main Furniture
    const dropzoneMueble = document.getElementById('dropzone-mueble');
    const muebleEmptyPrompt = document.getElementById('mueble-empty-prompt');
    const muebleThumbnailsGrid = document.getElementById('mueble-thumbnails-grid');
    const muebleCountBadge = document.getElementById('mueble-count-badge');

    // Zone 2: Wood Reference
    const dropzoneMadera = document.getElementById('dropzone-madera');
    const maderaEmptyPrompt = document.getElementById('madera-empty-prompt');
    const maderaPreviewCard = document.getElementById('madera-preview-card');
    const maderaPreviewImg = document.getElementById('madera-preview-img');
    const btnRemoveMadera = document.getElementById('btn-remove-madera');

    // Zone 3: Fabric Reference
    const dropzoneTela = document.getElementById('dropzone-tela');
    const telaEmptyPrompt = document.getElementById('tela-empty-prompt');
    const telaPreviewCard = document.getElementById('tela-preview-card');
    const telaPreviewImg = document.getElementById('tela-preview-img');
    const btnRemoveTela = document.getElementById('btn-remove-tela');

    // Action Controls
    const btnBorrar = document.getElementById('btn-borrar');
    const btnGenerar = document.getElementById('btn-generar');
    const loading = document.getElementById('loading');

    // Results & Multi-Card Container
    const resultArea = document.getElementById('result-area');
    const resultHeading = document.getElementById('result-heading');
    const resultVistasBadge = document.getElementById('result-vistas-badge');
    const btnCopiarTodo = document.getElementById('btn-copiar-todo');
    const cardsContainer = document.getElementById('cards-container') || document.getElementById('results-cards-container');

    // Main Buttons & Sub-panels
    const mainButtonsContainer = document.getElementById('main-buttons-container');
    const subVistas = document.getElementById('sub-vistas');
    const gridSubVistas = document.getElementById('grid-sub-vistas');
    const subEntorno = document.getElementById('sub-entorno');

    // Entorno Form Inputs
    const inputMedidas = document.getElementById('input-medidas');
    const inputTipoMueble = document.getElementById('input-tipo-mueble');
    const inputLugarMueble = document.getElementById('input-lugar-mueble');

    // -------------------------------------------------------------------------
    // State Registry
    // -------------------------------------------------------------------------
    const uploadState = {
        // Array of { id: string, file: File, previewUrl: string }
        muebleFiles: [],
        // { file: File, previewUrl: string } or null
        maderaFile: null,
        // { file: File, previewUrl: string } or null
        telaFile: null
    };

    const vistasModes = ['vistas', 'vistas + tela y madera', 'vistas + tela'];

    // -------------------------------------------------------------------------
    // Helper Utilities
    // -------------------------------------------------------------------------
    function generateId() {
        return 'file_' + Math.random().toString(36).substring(2, 9) + '_' + Date.now();
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    async function copyText(text, btnElement, successLabel = '¡Copiado!') {
        if (!text) return false;
        let ok = false;

        if (navigator.clipboard && navigator.clipboard.writeText) {
            try {
                await navigator.clipboard.writeText(text);
                ok = true;
            } catch (err) {
                ok = false;
            }
        }

        if (!ok) {
            try {
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.position = 'fixed';
                ta.style.left = '-9999px';
                ta.style.top = '0';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                ok = document.execCommand('copy');
                document.body.removeChild(ta);
            } catch (err) {
                ok = false;
            }
        }

        if (ok && btnElement) {
            const origHtml = btnElement.innerHTML;
            btnElement.innerText = successLabel;
            btnElement.classList.add('copied');
            setTimeout(() => {
                btnElement.innerHTML = origHtml;
                btnElement.classList.remove('copied');
            }, 2000);
        }

        return ok;
    }

    function updateActionButtons() {
        const hasAnyFile = uploadState.muebleFiles.length > 0 || !!uploadState.maderaFile || !!uploadState.telaFile;
        const canGenerate = uploadState.muebleFiles.length > 0;
        if (btnBorrar) btnBorrar.disabled = !hasAnyFile;
        if (btnGenerar) btnGenerar.disabled = !canGenerate;
    }

    // -------------------------------------------------------------------------
    // Zone 1: Main Furniture Multi-Upload & Gallery Logic
    // -------------------------------------------------------------------------
    function renderMuebleThumbnails() {
        if (!muebleThumbnailsGrid) return;
        muebleThumbnailsGrid.innerHTML = '';

        const count = uploadState.muebleFiles.length;

        if (count === 0) {
            muebleThumbnailsGrid.classList.add('hidden');
            if (muebleEmptyPrompt) muebleEmptyPrompt.classList.remove('hidden');
            if (dropzoneMueble) dropzoneMueble.classList.remove('has-images');
            if (muebleCountBadge) {
                muebleCountBadge.innerText = '0 fotos';
                muebleCountBadge.classList.remove('active');
            }
            return;
        }

        if (muebleEmptyPrompt) muebleEmptyPrompt.classList.add('hidden');
        muebleThumbnailsGrid.classList.remove('hidden');
        if (dropzoneMueble) dropzoneMueble.classList.add('has-images');

        if (muebleCountBadge) {
            muebleCountBadge.innerText = count === 1 ? '1 foto' : `${count} fotos`;
            muebleCountBadge.classList.add('active');
        }

        uploadState.muebleFiles.forEach((item) => {
            const card = document.createElement('div');
            card.className = 'thumb-card';
            card.dataset.id = item.id;

            const img = document.createElement('img');
            img.src = item.previewUrl;
            img.alt = item.file.name;
            img.className = 'thumb-img';

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'thumb-remove-btn';
            removeBtn.innerText = '✕';
            removeBtn.title = `Eliminar ${item.file.name}`;
            removeBtn.setAttribute('aria-label', `Eliminar ${item.file.name}`);
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                removeMuebleFile(item.id);
            });

            card.appendChild(img);
            card.appendChild(removeBtn);
            muebleThumbnailsGrid.appendChild(card);
        });
    }

    function addMuebleFiles(files) {
        const imageFiles = Array.from(files).filter(f => f.type.startsWith('image/'));
        if (imageFiles.length === 0) {
            alert('Por favor arrastra solo archivos de imagen (JPEG, PNG, WebP).');
            return;
        }

        imageFiles.forEach(file => {
            // Deduplicate by filename, filesize, and timestamp
            const exists = uploadState.muebleFiles.some(m =>
                m.file.name === file.name &&
                m.file.size === file.size &&
                m.file.lastModified === file.lastModified
            );
            if (!exists) {
                const previewUrl = URL.createObjectURL(file);
                uploadState.muebleFiles.push({
                    id: generateId(),
                    file: file,
                    previewUrl: previewUrl
                });
            }
        });

        renderMuebleThumbnails();
        updateActionButtons();
    }

    function removeMuebleFile(id) {
        const idx = uploadState.muebleFiles.findIndex(item => item.id === id);
        if (idx !== -1) {
            URL.revokeObjectURL(uploadState.muebleFiles[idx].previewUrl);
            uploadState.muebleFiles.splice(idx, 1);
            renderMuebleThumbnails();
            updateActionButtons();
        }
    }

    // Zone 1 Drag & Drop Events
    if (dropzoneMueble) {
        ['dragenter', 'dragover'].forEach(name => {
            dropzoneMueble.addEventListener(name, (e) => {
                e.preventDefault();
                dropzoneMueble.classList.add('dragover');
            });
        });

        dropzoneMueble.addEventListener('dragleave', (e) => {
            e.preventDefault();
            if (!dropzoneMueble.contains(e.relatedTarget)) {
                dropzoneMueble.classList.remove('dragover');
            }
        });

        dropzoneMueble.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzoneMueble.classList.remove('dragover');
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                addMuebleFiles(e.dataTransfer.files);
            }
        });
    }

    // -------------------------------------------------------------------------
    // Zone 2: Wood Reference Dropzone Logic
    // -------------------------------------------------------------------------
    function setMaderaFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Por favor arrastra un archivo de imagen para la textura de madera.');
            return;
        }

        if (uploadState.maderaFile) {
            URL.revokeObjectURL(uploadState.maderaFile.previewUrl);
        }

        uploadState.maderaFile = {
            file: file,
            previewUrl: URL.createObjectURL(file)
        };

        if (maderaPreviewImg) maderaPreviewImg.src = uploadState.maderaFile.previewUrl;
        if (maderaEmptyPrompt) maderaEmptyPrompt.classList.add('hidden');
        if (maderaPreviewCard) maderaPreviewCard.classList.remove('hidden');
        updateActionButtons();
    }

    function clearMaderaFile() {
        if (uploadState.maderaFile) {
            URL.revokeObjectURL(uploadState.maderaFile.previewUrl);
            uploadState.maderaFile = null;
        }
        if (maderaPreviewImg) maderaPreviewImg.src = '';
        if (maderaPreviewCard) maderaPreviewCard.classList.add('hidden');
        if (maderaEmptyPrompt) maderaEmptyPrompt.classList.remove('hidden');
        updateActionButtons();
    }

    if (dropzoneMadera) {
        ['dragenter', 'dragover'].forEach(name => {
            dropzoneMadera.addEventListener(name, (e) => {
                e.preventDefault();
                dropzoneMadera.classList.add('dragover');
            });
        });

        dropzoneMadera.addEventListener('dragleave', (e) => {
            e.preventDefault();
            if (!dropzoneMadera.contains(e.relatedTarget)) {
                dropzoneMadera.classList.remove('dragover');
            }
        });

        dropzoneMadera.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzoneMadera.classList.remove('dragover');
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                setMaderaFile(e.dataTransfer.files[0]);
            }
        });
    }

    if (btnRemoveMadera) {
        btnRemoveMadera.addEventListener('click', (e) => {
            e.stopPropagation();
            clearMaderaFile();
        });
    }

    // -------------------------------------------------------------------------
    // Zone 3: Fabric Reference Dropzone Logic
    // -------------------------------------------------------------------------
    function setTelaFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Por favor arrastra un archivo de imagen para la textura de tela.');
            return;
        }

        if (uploadState.telaFile) {
            URL.revokeObjectURL(uploadState.telaFile.previewUrl);
        }

        uploadState.telaFile = {
            file: file,
            previewUrl: URL.createObjectURL(file)
        };

        if (telaPreviewImg) telaPreviewImg.src = uploadState.telaFile.previewUrl;
        if (telaEmptyPrompt) telaEmptyPrompt.classList.add('hidden');
        if (telaPreviewCard) telaPreviewCard.classList.remove('hidden');
        updateActionButtons();
    }

    function clearTelaFile() {
        if (uploadState.telaFile) {
            URL.revokeObjectURL(uploadState.telaFile.previewUrl);
            uploadState.telaFile = null;
        }
        if (telaPreviewImg) telaPreviewImg.src = '';
        if (telaPreviewCard) telaPreviewCard.classList.add('hidden');
        if (telaEmptyPrompt) telaEmptyPrompt.classList.remove('hidden');
        updateActionButtons();
    }

    if (dropzoneTela) {
        ['dragenter', 'dragover'].forEach(name => {
            dropzoneTela.addEventListener(name, (e) => {
                e.preventDefault();
                dropzoneTela.classList.add('dragover');
            });
        });

        dropzoneTela.addEventListener('dragleave', (e) => {
            e.preventDefault();
            if (!dropzoneTela.contains(e.relatedTarget)) {
                dropzoneTela.classList.remove('dragover');
            }
        });

        dropzoneTela.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzoneTela.classList.remove('dragover');
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                setTelaFile(e.dataTransfer.files[0]);
            }
        });
    }

    if (btnRemoveTela) {
        btnRemoveTela.addEventListener('click', (e) => {
            e.stopPropagation();
            clearTelaFile();
        });
    }

    // -------------------------------------------------------------------------
    // Global Master Reset (Reset Absoluto)
    // -------------------------------------------------------------------------
    if (btnBorrar) {
        btnBorrar.addEventListener('click', () => {
            // Clean Zone 1
            uploadState.muebleFiles.forEach(item => URL.revokeObjectURL(item.previewUrl));
            uploadState.muebleFiles = [];
            renderMuebleThumbnails();

            // Clean Zone 2
            clearMaderaFile();

            // Clean Zone 3
            clearTelaFile();

            // Reset Output Area & Cards Container
            if (resultArea) resultArea.classList.add('hidden');
            if (cardsContainer) cardsContainer.innerHTML = '';
            if (loading) loading.classList.add('hidden');

            // Reset Main Buttons
            document.querySelectorAll('.main-btn').forEach(b => b.classList.remove('active'));

            // Hide dynamic sub-panels
            if (subVistas) subVistas.classList.add('hidden');
            if (subEntorno) subEntorno.classList.add('hidden');

            // Reset Sub-options Chips
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

            updateActionButtons();
        });
    }

    // -------------------------------------------------------------------------
    // Main Buttons & Sub-Panels Selection Logic
    // -------------------------------------------------------------------------
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

    if (gridSubVistas) {
        gridSubVistas.addEventListener('click', (e) => {
            const chip = e.target.closest('.sub-option-chip');
            if (!chip) return;
            gridSubVistas.querySelectorAll('.sub-option-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
        });
    }

    // -------------------------------------------------------------------------
    // Dynamic Multi-Card Output Rendering (R3)
    // -------------------------------------------------------------------------
    function normalizeOutputViews(data) {
        if (Array.isArray(data.vistas) && data.vistas.length > 0) {
            return data.vistas.map((item, idx) => ({
                titulo: item.titulo || item.title || `Vista ${idx + 1}`,
                prompt: item.prompt || item.text || ''
            }));
        }

        if (data.view_prompts && typeof data.view_prompts === 'object') {
            return Object.entries(data.view_prompts).map(([k, text]) => {
                const cleanTitle = k.replace(/^vista_/, '').replace(/_/g, ' ').toUpperCase();
                return {
                    titulo: cleanTitle,
                    prompt: text
                };
            });
        }

        if (data.prompt) {
            return [{
                titulo: 'Prompt Generado',
                prompt: data.prompt
            }];
        }

        return [];
    }

    function renderDynamicResults(data) {
        if (!resultArea || !cardsContainer) return;

        cardsContainer.innerHTML = '';
        const views = normalizeOutputViews(data);

        if (views.length === 0) {
            alert('No se generaron prompts en la respuesta.');
            return;
        }

        const isMulti = views.length > 1;

        if (resultHeading) {
            resultHeading.innerText = isMulti ? 'Prompts Generados:' : 'Prompt Generado:';
        }

        if (resultVistasBadge) {
            if (isMulti) {
                resultVistasBadge.innerText = `${views.length} vistas`;
                resultVistasBadge.classList.remove('hidden');
            } else {
                resultVistasBadge.classList.add('hidden');
            }
        }

        if (btnCopiarTodo) {
            if (isMulti) {
                btnCopiarTodo.classList.remove('hidden');
                btnCopiarTodo.onclick = () => {
                    const combined = views.map(v => `=== ${v.titulo} ===\n${v.prompt}\n`).join('\n');
                    copyText(combined, btnCopiarTodo, '¡Todas Copiadas!');
                };
            } else {
                btnCopiarTodo.classList.add('hidden');
            }
        }

        views.forEach((item, index) => {
            const card = document.createElement('article');
            card.className = 'view-card';

            const header = document.createElement('header');
            header.className = 'view-card-header';

            const titleWrap = document.createElement('div');
            titleWrap.className = 'view-card-title';
            titleWrap.innerHTML = `<span class="view-icon">📐</span> <h4>${escapeHtml(item.titulo)}</h4>`;

            const actions = document.createElement('div');
            actions.className = 'view-card-actions';

            const copyBtn = document.createElement('button');
            copyBtn.type = 'button';
            copyBtn.className = 'btn-copy-card';
            copyBtn.dataset.index = index;
            copyBtn.innerHTML = `<span>Copiar texto</span>`;

            copyBtn.addEventListener('click', () => {
                copyText(item.prompt, copyBtn, '¡Copiado!');
            });

            actions.appendChild(copyBtn);
            header.appendChild(titleWrap);
            header.appendChild(actions);

            const body = document.createElement('div');
            body.className = 'view-card-body';

            const textarea = document.createElement('textarea');
            textarea.className = 'view-card-textarea prompt-textarea-view';
            textarea.readOnly = true;
            textarea.rows = isMulti ? 7 : 10;
            textarea.value = item.prompt;

            body.appendChild(textarea);
            card.appendChild(header);
            card.appendChild(body);

            cardsContainer.appendChild(card);
        });

        resultArea.classList.remove('hidden');
    }

    // -------------------------------------------------------------------------
    // API Dispatch & Generation Logic
    // -------------------------------------------------------------------------
    if (btnGenerar) {
        btnGenerar.addEventListener('click', async () => {
            if (uploadState.muebleFiles.length === 0) {
                alert('Por favor carga al menos una imagen del mueble principal.');
                return;
            }

            // Active main button
            const activeMainBtn = document.querySelector('.main-btn.active');
            const botonPrincipal = activeMainBtn ? (activeMainBtn.dataset.boton || activeMainBtn.innerText.trim()) : '';

            // Sub-option if vistas mode
            let subOpcion = '';
            if (vistasModes.includes(botonPrincipal)) {
                const activeSubChip = document.querySelector('#grid-sub-vistas .sub-option-chip.active');
                subOpcion = activeSubChip ? (activeSubChip.dataset.sub || activeSubChip.innerText.trim()) : 'Frontal 0°';
            }

            // Entorno parameters
            let medidas = '';
            let tipoMueble = '';
            let lugarMueble = '';
            if (botonPrincipal === 'entorno') {
                if (inputMedidas) medidas = inputMedidas.value.trim();
                if (inputTipoMueble) tipoMueble = inputTipoMueble.value.trim();
                if (inputLugarMueble) lugarMueble = inputLugarMueble.value.trim();
            }

            const formData = new FormData();

            // Append all furniture images
            uploadState.muebleFiles.forEach(item => {
                formData.append('mueble_images', item.file);
            });

            // Append first furniture image as 'image' for legacy compatibility
            formData.append('image', uploadState.muebleFiles[0].file);

            // Append optional wood reference
            if (uploadState.maderaFile) {
                formData.append('madera_image', uploadState.maderaFile.file);
                formData.append('madera', uploadState.maderaFile.file.name);
            } else {
                formData.append('madera', '');
            }

            // Append optional fabric reference
            if (uploadState.telaFile) {
                formData.append('tela_image', uploadState.telaFile.file);
                formData.append('tela', uploadState.telaFile.file.name);
            } else {
                formData.append('tela', '');
            }

            // Action parameters
            formData.append('boton_principal', botonPrincipal);
            formData.append('sub_opcion', subOpcion);
            formData.append('medidas', medidas);
            formData.append('tipo_mueble', tipoMueble);
            formData.append('lugar_mueble', lugarMueble);

            // Legacy backward compatibility fields
            formData.append('vista', subOpcion || botonPrincipal || 'Frontal');
            formData.append('ambiente', '');

            // Update UI during dispatch
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
                    renderDynamicResults(data);
                } else {
                    alert('Error: ' + (data.error || 'No se pudo generar el prompt.'));
                }
            } catch (err) {
                alert('Error de conexión al servidor al generar el prompt.');
            } finally {
                btnGenerar.disabled = uploadState.muebleFiles.length === 0;
                if (loading) loading.classList.add('hidden');
            }
        });
    }
});
