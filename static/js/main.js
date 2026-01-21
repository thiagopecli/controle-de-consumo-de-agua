// Main JavaScript file
console.log('Sistema de Controle de Consumo de Água carregado');

// Funções auxiliares
function formatarData(data) {
    return new Date(data).toLocaleDateString('pt-BR');
}

function formatarDataHora(data) {
    return new Date(data).toLocaleString('pt-BR');
}

function formatarNumero(numero, casasDecimais = 3) {
    return parseFloat(numero).toFixed(casasDecimais);
}

// Exportar funções
window.formatarData = formatarData;
window.formatarDataHora = formatarDataHora;
window.formatarNumero = formatarNumero;
