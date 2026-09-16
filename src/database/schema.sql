-- 1. users — no dependencies
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    full_name     VARCHAR NOT NULL,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- 2. skin_tone_anchor — no dependencies
CREATE TABLE skin_tone_anchor (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR NOT NULL,
    reference_color VARCHAR(7) NOT NULL
);

-- 3. seller — depends on users (one-to-one)
CREATE TABLE seller (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER UNIQUE NOT NULL REFERENCES users(id),
    business_name VARCHAR NOT NULL,
    phone_number  VARCHAR NOT NULL,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- 4. brand — depends on seller (one-to-many)
CREATE TABLE brand (
    id          SERIAL PRIMARY KEY,
    seller_id   INTEGER NOT NULL REFERENCES seller(id),
    name        VARCHAR NOT NULL,
    description TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 5. product — depends on brand (one-to-many)
CREATE TABLE product (
    id          SERIAL PRIMARY KEY,
    brand_id    INTEGER NOT NULL REFERENCES brand(id),
    name        VARCHAR NOT NULL,
    category    VARCHAR DEFAULT 'lipstick' NOT NULL,
    description TEXT NOT NULL,
    image_path  VARCHAR NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 6. shade — depends on product (one-to-many)
CREATE TABLE shade (
    id                  SERIAL PRIMARY KEY,
    product_id          INTEGER NOT NULL REFERENCES product(id),
    name                VARCHAR NOT NULL,
    finish              VARCHAR NOT NULL CHECK (finish IN ('matte', 'glossy')),
    base_pigment_color  VARCHAR(7) NOT NULL,
    swatch_image_path   TEXT NOT NULL,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- 7. shade_render_profile — depends on shade + skin_tone_anchor
CREATE TABLE shade_render_profile (
    id                    SERIAL PRIMARY KEY,
    shade_id              INTEGER NOT NULL REFERENCES shade(id),
    skin_tone_anchor_id   INTEGER NOT NULL REFERENCES skin_tone_anchor(id),
    render_color          VARCHAR(7) NOT NULL,
    computed_at           TIMESTAMP DEFAULT NOW(),
    UNIQUE (shade_id, skin_tone_anchor_id)
);

-- 8. tryon_session — depends on users (nullable, for guests) + skin_tone_anchor + shade
CREATE TABLE tryon_session (
    id                    SERIAL PRIMARY KEY,
    user_id               INTEGER REFERENCES users(id),
    skin_tone_anchor_id   INTEGER NOT NULL REFERENCES skin_tone_anchor(id),
    shade_id              INTEGER NOT NULL REFERENCES shade(id),
    skin_tone_source      VARCHAR NOT NULL CHECK (skin_tone_source IN ('manual_override', 'auto_detected')),
    started_at            TIMESTAMP DEFAULT NOW(),
    ended_at              TIMESTAMP
);