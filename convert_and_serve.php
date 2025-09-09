<?php
// convert_and_serve.php

// Папка для временных PDF
$tmpDir = '/tmp/kodexplorer_pdf';

// Проверяем, что папка существует и доступна
if (!is_dir($tmpDir) || !is_writable($tmpDir)) {
    http_response_code(500);
    echo "Ошибка: временная папка недоступна";
    exit;
}

// Получаем путь к исходному файлу из GET-параметра
// Например: convert_and_serve.php?file=/var/www/html/data/docs/example.docx
if (!isset($_GET['file'])) {
    http_response_code(400);
    echo "Ошибка: параметр file не задан";
    exit;
}

$inputFile = $_GET['file'];

// Безопасность: проверяем, что файл существует и расширение допустимо
$allowedExt = ['docx', 'xlsx', 'doc', 'xls'];
$ext = strtolower(pathinfo($inputFile, PATHINFO_EXTENSION));

if (!in_array($ext, $allowedExt)) {
    http_response_code(400);
    echo "Ошибка: неподдерживаемый формат файла";
    exit;
}

if (!file_exists($inputFile)) {
    http_response_code(404);
    echo "Ошибка: файл не найден";
    exit;
}

// Формируем имя PDF-файла во временной папке
$baseName = basename($inputFile, '.' . $ext);
$outputFile = $tmpDir . '/' . $baseName . '.pdf';

// Команда конвертации через LibreOffice
// --headless — без GUI
// --convert-to pdf — конвертация в PDF
// --outdir — папка вывода
$cmd = 'libreoffice --headless --convert-to pdf --outdir ' . escapeshellarg($tmpDir) . ' ' . escapeshellarg($inputFile) . ' 2>&1';

// Выполняем команду
exec($cmd, $output, $return_var);

if ($return_var !== 0 || !file_exists($outputFile)) {
    http_response_code(500);
    echo "Ошибка конвертации файла в PDF";
    exit;
}

// Отдаём PDF пользователю с заголовками
header('Content-Type: application/pdf');
header('Content-Disposition: inline; filename="' . $baseName . '.pdf"');
header('Content-Length: ' . filesize($outputFile));

// Читаем и выводим файл
readfile($outputFile);

// Удаляем PDF после отдачи
unlink($outputFile);

exit;