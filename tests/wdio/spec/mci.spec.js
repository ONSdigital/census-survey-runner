import chai from 'chai'
const expect = chai.expect
const getUri = uri => 'http://localhost:5000/' + uri

describe('MCI test', function() {
  before((done) => {
    browser
      .url('/dev')
      .waitForExist('.qa-select-schema')
    browser
      .selectByValue('.qa-select-schema', '1_0205.json')
      .submitForm('form')
    browser
      .url('/questionnaire')
  })

  it('The questionnaire page has been reached', function() {
    expect(browser.url().value).to.equal(getUri('questionnaire'))
  })

  it('The form can be filled in and submitted', function() {
    const inputs = browser.elements('.input-type--currency .input')
    browser
      .setValue('#6fd644b0-798e-4a58-a393-a438b32fe637-year', '2016')
      .setValue('#06a6a4b7-6ce4-4687-879d-3443cd8e2ff0-year', '2017')
    inputs.setValue(2000)
    browser.submitForm('form')
    expect(browser.url().value).to.equal(getUri('submission'))
  })

  it('The survery can be completed with "thankyou page" reached', function() {
    browser.submitForm('form')
    expect(browser.url().value).to.equal(getUri('thank-you'))
  })
})
