const input = document.getElementById('input');
function checkZipCode() {
    let zip = input.value;
    const zipRegex = /^\d{5}$/;
    const zipValid = zipRegex.test(zip);
    const errorLabel = document.getElementById('error-label');
    errorLabel.style.position = 'absolute';
    errorLabel.style.color = '#ffaaaa';

    if (zipValid || zip === '') {
        errorLabel.innerText = '';
    }
    else {
        errorLabel.innerText = 'Invalid zip code.';
    }
}

input.addEventListener('keyup', setInterval(checkZipCode, 100));