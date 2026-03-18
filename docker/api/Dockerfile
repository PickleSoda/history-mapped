FROM php:8.3-fpm-bookworm

RUN apt-get update && apt-get install -y \
    curl \
    git \
    libfreetype6-dev \
    libicu-dev \
    libjpeg62-turbo-dev \
    libonig-dev \
    libpng-dev \
    libpq-dev \
    libxml2-dev \
    libzip-dev \
    unzip \
    zip \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install \
    bcmath \
    exif \
    gd \
    intl \
    pcntl \
    pdo_pgsql \
    zip \
    && pecl install redis \
    && docker-php-ext-enable redis \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html

CMD ["php-fpm"]
