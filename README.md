Prosty agregator newsów opierający się na feedach RSS.
Korzysta on z bazy danych SQLite
### Instalacja
1. Sklonuj repozytorium na swój komputer
2. Zainstaluj potrzebne biblioteki poleceniem `pip install -r requirements.txt`
3. W katalogu głównym repozytorium dokonaj potrzebnych migracji, poleceniami
`python manage.py makemigrations feed`, oraz `python manage.py migrate`