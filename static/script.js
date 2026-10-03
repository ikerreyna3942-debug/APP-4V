const dropzone = document.getElementById('dropzone');
const imagePreview = document.getElementById('image-preview');
const btnBorrar = document.getElementById('btn-borrar');
const btnGenerar = document.getElementById('btn-generar');
const loading = document.getElementById('loading');
const resultArea = document.getElementById('result-area');
const promptOutput = document.getElementById('prompt-output');
const btnCopiar = document.getElementById('btn-copiar');

let currentFile = null;

// Modifiers Logic
document.querySelectorAll('.btn-group').forEach(group => {
    group.addEventListener('click', e => {
        if (e.target.classList.contains('mod-btn')) {
            const btns = group.querySelectorAll('.mod-btn');
            const isActive = e.target.classList.contains('active');
            
            // Allow deselect for all except vista/ambiente (if they need default)
            btns.forEach(b => b.classList.remove('active'));
            if (!isActive) {
                e.target.classList.add('active');
            }
        }
    });
});

// Drag & Drop strict logic
dropzone.addEventListener('dragover', e => {
    e.preventDefault();
    dropzone.classList.add('dragover');
});

dropzone.addEventListener('dragleave', e => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
});

dropzone.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        if (file.type.startsWith('image/')) {
            currentFile = file;
            const reader = new FileReader();
            reader.onload = ev => {
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

// Absolute Reset Button
btnBorrar.addEventListener('click', () => {
    currentFile = null;
    imagePreview.src = '';
    imagePreview.classList.add('hidden');
    btnBorrar.disabled = true;
    btnGenerar.disabled = true;
    resultArea.classList.add('hidden');
    promptOutput.value = '';
    
    // Reset modifiers to default
    document.querySelectorAll('.mod-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('#group-vistas .mod-btn[data-val="Frontal"]').classList.add('active');
    document.querySelector('#group-ambientes .mod-btn[data-val="Minimalista puro (sin sombras)"]').classList.add('active');
});

// Generate Prompt
btnGenerar.addEventListener('click', async () => {
    if (!currentFile) return;
    
    const vista = document.querySelector('#group-vistas .active')?.dataset.val || '';
    const tela = document.querySelector('#group-telas .active')?.dataset.val || '';
    const madera = document.querySelector('#group-maderas .active')?.dataset.val || '';
    const ambiente = document.querySelector('#group-ambientes .active')?.dataset.val || '';
    
    const formData = new FormData();
    formData.append('image', currentFile);
    formData.append('vista', vista);
    formData.append('tela', tela);
    formData.append('madera', madera);
    formData.append('ambiente', ambiente);
    
    btnGenerar.disabled = true;
    loading.classList.remove('hidden');
    resultArea.classList.add('hidden');
    
    try {
        const res = await fetch('/api/generate', {
            method: 'POST',
            body: formData
        });
        
        const data = await res.json();
        
        if (data.success) {
            promptOutput.value = data.prompt;
            resultArea.classList.remove('hidden');
        } else {
            alert('Error: ' + data.error);
        }
    } catch (err) {
        alert('Error de conexión al servidor.');
    } finally {
        btnGenerar.disabled = false;
        loading.classList.add('hidden');
    }
});

// Copy button
btnCopiar.addEventListener('click', () => {
    promptOutput.select();
    document.execCommand('copy');
    const og = btnCopiar.innerText;
    btnCopiar.innerText = '¡Copiado!';
    setTimeout(() => btnCopiar.innerText = og, 2000);
});
