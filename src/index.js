/**
 * Retrieves the response from the ML model
 * @param {String} data the ZIP code to be searched
 * @returns {JSON} response
 */
const getResponse = (data) => {

    // TODO: Implement this function
    return data;
};

/**
 * Displays the response in the HTML
 * @param {JSON} response 
 */
const displayResponse = (response) => {
    // TODO: Implement this function
};

const button = document.getElementById('search-button');
const results = document.querySelector('.result');
/**
 * Event listener for the search button
 * On click, it retrieves the data from the ML model and displays it in the HTML
 */
button.addEventListener('click', () => {

    const data = document.getElementById('data').value;
    // console.log(data);

    const response = getResponse(data);

    // TODO: Display the response in the HTML
    displayResponse(response);

});