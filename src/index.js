function checkZipCode() {
    const zip = document.getElementById('input').value;
    const zipRegex = /^\d{5}$/;
    const zipValid = zipRegex.test(zip);
    const errorLabel = document.getElementById('error-label');
    errorLabel.style.position = 'absolute';
    errorLabel.style.color = 'red';

    if (zipValid) {
        errorLabel.innerText = '';
    }
    else {
        errorLabel.innerText = 'Invalid zip code.';
    }
}

setInterval(checkZipCode, 50);