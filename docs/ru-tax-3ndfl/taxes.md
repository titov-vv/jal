### Инструкция по подготовке данных для декларации 3-НДФЛ для Interactive Brokers

1. Нужно получить flex-отчет по всем операциям в формате XML.  
Для этого необходимо в личном кабинете Interactive Brokers выбрать заздел *Reports / Tax Docs*. 
На появившейся странице *Reports* нужно выбрать закладку *Flex Queries*. В разделе *Activity Flex Query* нужно нажать *'+'* чтобы создать новый отчёт.
Далее необходимо выполнить настройку отчета:
    - *Query name* - нужно указать уникальное имя отчёта
    - *Sections* - нужно отменить необходимые секции отчета. Минимально необходимы: *Account Information, Cash Transactions, Corporate Actions, Option Exercises, Assignments and Expirations, Trades, Transactions Fees, Transfers*
    - *Format* - XML
    - *Date Format* - yyyyMMdd
    - *Time Format* - HHmmss
    - *Date/Time separator* - ;(semi-colon)
    - *Profit and Loss* - Default
    - на вопросы *Include Canceled Trades?, Include Currency Rates?, Display Account Alias in Place of Account ID?, Breakout by Day?* ответить No.  
    После этого нажать *Continue* и затем *Create*  
2. Вновь созданный flex-отчет появится в списке *Activity Flex Query*. Его нужно запустить по нажатию на стрелку вправо (команда *Run*).
Формат нужно оставить XML. В качестве периодна максимум можно выбрать год - поэтому нужно выполнить отчет несколько раз, чтобы последовательно получить операции за всё время существования счёта.
В результате у вас будет один или несколько XML файлов с отчетами. В качестве примера для дальнейших действий я буду использовать [IBKR_flex_sample.xml](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/IBKR_flex_sample.xml)
3. ... продолжение следует ... 