#include "display_direct.h"

#include "ch32v00x.h"
#include "display_hw.h"

#define MODIFY_REG(REG, CLEARMASK, SETMASK) ((REG) = (((REG) & (~(CLEARMASK))) | (SETMASK)))

extern volatile uint32_t system_clock;

static size_t glyph_index_or_space(wchar_t ch)
{
    size_t space_index = 0;

    for(size_t i = 0; i < GLYPH_LEN; ++i)
    {
        if(FONT_8x8[i].ch == ch)
        {
            return i;
        }
    }

    return space_index;
}

static size_t prepare_glyph_indices(const wchar_t *str, size_t str_cap, size_t *out_indices)
{
    size_t str_len = wcslen(str);

    if(str_cap == 0)
    {
        return 0;
    }

    if(str_len >= str_cap)
    {
        str_len = str_cap - 1;
    }

    if(str_len == 0)
    {
        out_indices[0] = glyph_index_or_space(L' ');
        return 1;
    }

    for(size_t i = 0; i < str_len; ++i)
    {
        out_indices[i] = glyph_index_or_space(str[i]);
    }

    return str_len;
}

struct gpio_drive_masks
{
    uint32_t a;
    uint32_t c;
    uint32_t d;
};

static inline struct gpio_drive_masks calculate_drive_masks(uint8_t column_bits)
{
    struct gpio_drive_masks masks = {GPIOA_SET_MASK, GPIOC_SET_MASK, GPIOD_SET_MASK};

    for(size_t row = 0; row < 8; ++row)
    {
        if((column_bits & (1U << row)) == 0)
        {
            continue;
        }

        switch(row_drive_lines[row].gpio_base)
        {
            case GPIOA_BASE:
                masks.a |= 1<<row_drive_lines[row].pin;
                break;
            case GPIOC_BASE:
                masks.c |= 1<<row_drive_lines[row].pin;
                break;
            case GPIOD_BASE:
                masks.d |= 1<<row_drive_lines[row].pin;
                break;
            default:
                printf("Fatal Error\r\n");
                while(1);
        }
    }

    return masks;
}

static inline void drive_display_column(uint8_t column_bits, size_t column_index)
{
    const struct gpio_drive_masks masks = calculate_drive_masks(column_bits);
    const size_t previous_column = (column_index + 7U) & 0x7U;

    ((GPIO_TypeDef*)(column_sink_lines[previous_column].gpio_base))->OUTDR |= 1<<column_sink_lines[previous_column].pin;

    MODIFY_REG(GPIOA->OUTDR, GPIOA_CLEAR_MASK, masks.a);
    MODIFY_REG(GPIOC->OUTDR, GPIOC_CLEAR_MASK, masks.c);
    MODIFY_REG(GPIOD->OUTDR, GPIOD_CLEAR_MASK, masks.d);

    ((GPIO_TypeDef*)(column_sink_lines[column_index].gpio_base))->OUTDR &= ~(1<<column_sink_lines[column_index].pin);
}

static void build_scroll_frame(uint8_t *frame, const size_t *glyph_indices, size_t glyph_count, size_t glyph_index, size_t column_offset)
{
    size_t dest_col = 0;
    const Glyph8x8 *current_glyph = &FONT_8x8[glyph_indices[glyph_index]];

    for(size_t col = column_offset; col < 8 && dest_col < 8; ++col, ++dest_col)
    {
        frame[dest_col] = current_glyph->columns[col];
    }

    if(dest_col >= 8)
    {
        return;
    }

    if(glyph_index + 1 < glyph_count)
    {
        const Glyph8x8 *next_glyph = &FONT_8x8[glyph_indices[glyph_index + 1]];
        for(size_t col = 0; dest_col < 8; ++col, ++dest_col)
        {
            frame[dest_col] = next_glyph->columns[col];
        }
    }
    else
    {
        while(dest_col < 8)
        {
            frame[dest_col++] = 0;
        }
    }
}


void render_loop(const wchar_t *str, size_t str_cap, uint32_t animation_time, uint32_t total_count)
{
    size_t glyph_indices[str_cap];
    size_t glyph_count = prepare_glyph_indices(str, str_cap, glyph_indices);

    if(glyph_count == 0)
    {
        return;
    }

    size_t glyph_cursor = 0;

    uint32_t count = 0;
    while(count < total_count)
    {
        uint32_t animation_timestamp = system_clock + animation_time;
        while(system_clock < animation_timestamp)
        {
            for(size_t i = 0; i < 8; i++)
            {
                drive_display_column(FONT_8x8[glyph_indices[glyph_cursor]].columns[i], i);
            }
        }

        if(glyph_cursor + 1 == glyph_count)
        {
            count++;
        }
        glyph_cursor = (glyph_cursor + 1) % glyph_count;
    }
}

void render_scroll_loop(const wchar_t *str, size_t str_cap, uint32_t animation_time, uint32_t total_count)
{
    size_t glyph_indices[str_cap];
    size_t glyph_count = prepare_glyph_indices(str, str_cap, glyph_indices);

    if(glyph_count == 0)
    {
        return;
    }

    uint8_t column_frame[8];
    build_scroll_frame(column_frame, glyph_indices, glyph_count, 0, 0);

    size_t scroll_column_index = 0;
    const size_t total_scroll_columns = glyph_count * 8;

    uint32_t count = 0;
    while(count < total_count)
    {
        uint32_t animation_timestamp = system_clock + animation_time;
        while(system_clock < animation_timestamp)
        {
            for(size_t i = 0; i < 8; i++)
            {
                drive_display_column(column_frame[i], i);
            }
        }

        if(scroll_column_index + 1 == total_scroll_columns)
        {
            count++;
        }
        scroll_column_index = (scroll_column_index + 1) % total_scroll_columns;

        size_t scroll_glyph_index = scroll_column_index / 8;
        size_t glyph_column_offset = scroll_column_index % 8;

        build_scroll_frame(column_frame, glyph_indices, glyph_count, scroll_glyph_index, glyph_column_offset);
    }
}

void display_direct_init(void)
{
    RCC->APB2PCENR |= RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC | RCC_APB2Periph_GPIOD | RCC_AFIOEN;

    for(size_t i = 0; i < 8; ++i)
    {
        GPIO_TypeDef *drive_port = (GPIO_TypeDef *)row_drive_lines[i].gpio_base;
        uint32_t drive_pin = row_drive_lines[i].pin;
        MODIFY_REG(drive_port->CFGLR, 0xFU << (drive_pin * 4), 0b0011U << (drive_pin * 4)); // push-pull output

        GPIO_TypeDef *sink_port = (GPIO_TypeDef *)column_sink_lines[i].gpio_base;
        uint32_t sink_pin = column_sink_lines[i].pin;
        MODIFY_REG(sink_port->CFGLR, 0xFU << (sink_pin * 4), 0b0011U << (sink_pin * 4)); // push-pull output
    }

    MODIFY_REG(AFIO->PCFR1, AFIO_PCFR1_SWJ_CFG, AFIO_PCFR1_SWJ_CFG_DISABLE);
}
