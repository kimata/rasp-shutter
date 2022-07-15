describe('Access Test', function() {
    it('can access top page', function() {
        cy.visit('/rasp-shutter/')
        cy.get('h2').eq(2).should('contain', '実行ログ')
  })
})
