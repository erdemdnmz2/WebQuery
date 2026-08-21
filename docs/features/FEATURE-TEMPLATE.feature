Feature: <Kullanıcıya sağlanan davranış>
  <İş değerini kısa biçimde açıklayın.>

  Background:
    Given <tüm senaryolarda geçerli başlangıç koşulu>

  Rule: <İş kuralı adı>
    <Kuralın kısa açıklaması.>

    Scenario: AC-01 - <Başarılı davranış>
      Given <başlangıç durumu>
      When <kullanıcı veya sistem eylemi>
      Then <doğrulanabilir sonuç>

    Scenario Outline: AC-02 - <Parametreli sınır veya hata davranışı>
      Given <başlangıç durumu>
      When <eylem, "<değer>" ile yapılır>
      Then <sonuç "<beklenen>" olmalıdır>

      Examples:
        | değer | beklenen |
        | <...> | <...> |
