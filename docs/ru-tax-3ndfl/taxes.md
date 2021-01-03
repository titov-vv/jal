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
3. В *jal* все транзакции привязаны к тому или иному счету. Поэтому для успешной загрузки отчёта вам нужно заранее создать как минимум пару счетов через меню *Data->Accounts* (в русской версии *Данные->Счета*):
    - счет типа *Investment*, у которого номер и валюта будут совпадать с номером и валютой счета Interactive Brokers. В моём примере я использую U1234567 и USD:  
    ![IBRK account](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/img/ibkr_account.png?raw=true) 
    - ещё один счет любого типа - он будет необходим для учета транзакций ввода/вывода дережных средств. Например:  
    ![Bank account](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/img/bank_account.png?raw=true)  
4. Непосредственно для загрузки отчёта вам необходимо выбрать пункт меню *Import->Broker statement...* (в русской версии *Импорт->Отчет брокера...*), после чего указать XML файл, который необходимо загрузить.
Если ваш отчет содержит транзации ввода/вывода денежных средств, то вы *jal* попросит вас указать какой счет нужно использовать для списания/зачисленя этих средств, например:  
![Select account](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/img/account_selection.png?raw=true)  
В случае успешного импорта, вы увидите сообщение *IB Flex-statement loaded successfully* на закладке *Log messages* (в русской версии *Сообщения*)  
![Import success](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/img/import_log.png?raw=true)
5. После загрузки вы можете выбрать полный интервал времени и нужный счёт, чтобы проверить корректность импорта данных:  
![Main window](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/img/main_window.png?raw=true)
6. При подготовке декларации все суммы нужно пересчитать в рубли - для этого необходимо загрузить курсы валют.
Сделать это можно с помощью меню *Load->Load quotes...* (в русской версии *Загрузить->Загрузить Котировки...*) и указав необходимый диапазон дат:  
![Quotes](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/img/update_quotes.png?raw=true)
7. ... продолжение следует ...