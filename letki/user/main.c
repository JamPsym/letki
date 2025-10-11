#include "ch32v00x.h"
#include "debug.h"

#include <wchar.h>

#define MODIFY_REG(REG, CLEARMASK, SETMASK) ((REG) = (((REG) & (~(CLEARMASK))) | (SETMASK)))
#define SET_BIT(REG, BIT) ((REG) |= (BIT))
#define CLEAR_BIT(REG, BIT) ((REG) &= ~(BIT))

typedef struct { wchar_t ch; uint8_t columns[8]; } Glyph8x8;

const Glyph8x8 FONT_8x8[] = {
  // --- BASE LATIN (A–Z + space) ---
  {L'A',{0x00,0xFE,0x11,0x11,0x11,0xFE,0x00,0x00}},
  {L'B',{0x00,0xFF,0x91,0x91,0x91,0x6E,0x00,0x00}},
  {L'C',{0x00,0x7E,0x81,0x81,0x81,0x66,0x00,0x00}},
  {L'D',{0x00,0xFF,0x81,0x81,0x81,0x7E,0x00,0x00}},
  {L'E',{0x00,0xFF,0x91,0x91,0x91,0x81,0x00,0x00}},
  {L'F',{0x00,0xFF,0x11,0x11,0x11,0x01,0x00,0x00}},
  {L'G',{0x00,0x7E,0x81,0x81,0x89,0x7A,0x00,0x00}},
  {L'H',{0x00,0xFF,0x10,0x10,0x10,0xFF,0x00,0x00}},
  {L'I',{0x00,0x81,0x81,0xFF,0x81,0x81,0x00,0x00}},
  {L'J',{0x00,0x60,0x80,0x81,0x81,0x7F,0x00,0x00}},
  {L'K',{0x00,0xFF,0x10,0x28,0x44,0x83,0x00,0x00}},
  {L'L',{0x00,0xFF,0x80,0x80,0x80,0x80,0x00,0x00}},
  {L'M',{0x00,0xFF,0x08,0x30,0x08,0xFF,0x00,0x00}},
  {L'N',{0x00,0xFF,0x08,0x10,0x20,0xFF,0x00,0x00}},
  {L'O',{0x00,0x7E,0x81,0x81,0x81,0x7E,0x00,0x00}},
  {L'P',{0x00,0xFF,0x11,0x11,0x11,0x0E,0x00,0x00}},
  {L'Q',{0x00,0x7E,0x81,0x81,0x85,0xFF,0x00,0x00}},
  {L'R',{0x00,0xFF,0x11,0x31,0x51,0x8E,0x00,0x00}},
  {L'S',{0x00,0x4E,0x91,0x91,0x91,0x62,0x00,0x00}},
  {L'T',{0x00,0x01,0x01,0xFF,0x01,0x01,0x00,0x00}},
  {L'U',{0x00,0x7F,0x80,0x80,0x80,0x7F,0x00,0x00}},
  {L'V',{0x00,0x3F,0x40,0x80,0x40,0x3F,0x00,0x00}},
  {L'W',{0x00,0xFF,0x40,0x38,0x40,0xFF,0x00,0x00}},
  {L'X',{0x00,0xC3,0x24,0x18,0x24,0xC3,0x00,0x00}},
  {L'Y',{0x00,0x0F,0x10,0xE0,0x10,0x0F,0x00,0x00}},
  {L'Z',{0x00,0xC1,0xA1,0x91,0x89,0x87,0x00,0x00}},
  {L' ',{0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00}},

  // --- POLISH LETTERS (8×8, UPPERCASE STYLE) ---
  {L'Ą',{0x00,0x7E,0x11,0x11,0x11,0x7E,0xC0,0x00}}, // tail bottom-left
  {L'Ć',{0x00,0x7C,0x82,0x82,0x82,0x4C,0x80,0x01}}, // acute top-right
  {L'Ę',{0x00,0x7F,0x51,0x51,0xD1,0x41,0x00,0x00}}, // tail bottom-left
  {L'Ł',{0x00,0xFF,0x88,0x98,0x8C,0x80,0x00,0x00}}, // stroke mid
  {L'Ń',{0x00,0xFF,0x10,0x08,0x04,0xFF,0x02,0x01}}, // acute top-right
  {L'Ó',{0x00,0x7C,0x82,0x82,0x82,0x7C,0x80,0x01}}, // acute top-right
  {L'Ś',{0x00,0x4C,0x92,0x92,0x93,0x64,0x00,0x00}}, // acute top-right
  {L'Ź',{0x00,0xC2,0xA2,0x92,0x8B,0x86,0x00,0x00}}, // acute top-right
  {L'Ż',{0x00,0x62,0x52,0x4B,0x47,0x42,0x00,0x00}}  // dot top-center
};
const size_t GLYPH_LEN = sizeof(FONT_8x8)/sizeof(FONT_8x8[0]);

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




// ones  D2 A1 C3 C4 D4 D3 C0 D7
struct active_line_struct {uint32_t gpio_base; uint32_t bitmask;};
struct active_line_struct ones[] = {
    {GPIOD_BASE, GPIO_OUTDR_ODR2},
    {GPIOA_BASE, GPIO_OUTDR_ODR1},
    {GPIOC_BASE, GPIO_OUTDR_ODR3},
    {GPIOC_BASE, GPIO_OUTDR_ODR4},
    {GPIOD_BASE, GPIO_OUTDR_ODR4},
    {GPIOD_BASE, GPIO_OUTDR_ODR3},
    {GPIOC_BASE, GPIO_OUTDR_ODR0},
    {GPIOD_BASE, GPIO_OUTDR_ODR7},
}; 
// zeros A2 C1 C2 C5 C6 C7 D0 D1
struct active_line_struct zeros[] = {
    {GPIOA_BASE, GPIO_OUTDR_ODR2},
    {GPIOC_BASE, GPIO_OUTDR_ODR1},
    {GPIOC_BASE, GPIO_OUTDR_ODR2},
    {GPIOC_BASE, GPIO_OUTDR_ODR5},
    {GPIOC_BASE, GPIO_OUTDR_ODR6},
    {GPIOC_BASE, GPIO_OUTDR_ODR7},
    {GPIOD_BASE, GPIO_OUTDR_ODR0},
    {GPIOD_BASE, GPIO_OUTDR_ODR1},
}; 


// masks to turn off leds
#define GPIOA_CLEAR_MASK 0x2 // A 1
#define GPIOC_CLEAR_MASK 0x19 // C 0 3 4
#define GPIOD_CLEAR_MASK 0x9C // D 2 3 4 7
#define GPIOA_SET_MASK 0x4 // A 2
#define GPIOC_SET_MASK 0xE6 // C 1 2 5 6 7
#define GPIOD_SET_MASK 0x3 // D 0 1

static void config_gpios();

void render_loop(const wchar_t* str, const size_t str_cap);

void render_loop_shifting(const wchar_t* str, const size_t str_cap);

int main(void)
{
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_1);
    SystemCoreClockUpdate();
    Delay_Init();
    USART_Printf_Init(115200);
    printf("USART debug ready\r\n");

    config_gpios();

    // ones  D2 A1 C3 C4 D4 D3 C0 D7
    GPIOA->OUTDR |= GPIO_OUTDR_ODR1;
    GPIOC->OUTDR |= GPIO_OUTDR_ODR3 | GPIO_OUTDR_ODR4 | GPIO_OUTDR_ODR0;
    GPIOD->OUTDR |= GPIO_OUTDR_ODR2 | GPIO_OUTDR_ODR4 | GPIO_OUTDR_ODR3 | GPIO_OUTDR_ODR7;
    // zeros A2 C1 C2 C5 C6 C7 D0 D1
    GPIOA->OUTDR &= ~GPIO_OUTDR_ODR2;
    GPIOC->OUTDR &= ~(GPIO_OUTDR_ODR1 | GPIO_OUTDR_ODR2 | GPIO_OUTDR_ODR5 | GPIO_OUTDR_ODR6 | GPIO_OUTDR_ODR7);
    GPIOD->OUTDR &= ~(GPIO_OUTDR_ODR0 | GPIO_OUTDR_ODR1);
 
    // kill swd :< 
    RCC->APB2PCENR |= RCC_AFIOEN;
    AFIO->PCFR1 |= AFIO_PCFR1_SWJ_CFG_DISABLE;

    const wchar_t str[] = L" WIDZEW WIDZEW ŁÓDZKI WIDZEW JA TEJ KURWY NIENAWIDZĘ  ";
    const size_t str_cap = sizeof(str) / sizeof(str[0]);
    render_loop_shifting(str, str_cap);

}

void config_gpios()
{
    RCC->APB2PCENR |= RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC | RCC_APB2Periph_GPIOD;


    // pwms 
    // D2 T1CH1
    GPIOD->CFGLR |= GPIO_CFGLR_MODE2;
    GPIOD->CFGLR &= ~GPIO_CFGLR_CNF2;
    // A1 T1CH2
    GPIOA->CFGLR |= GPIO_CFGLR_MODE1;
    GPIOA->CFGLR &= ~GPIO_CFGLR_CNF1;
    // C3 T1CH3
    // C4 T1CH4
    GPIOC->CFGLR |= GPIO_CFGLR_MODE3 | GPIO_CFGLR_MODE4;
    GPIOC->CFGLR &= ~(GPIO_CFGLR_CNF3 | GPIO_CFGLR_CNF4);

    // D4 T2CH1ETR ?
    // D3 T2CH2
    GPIOD->CFGLR |= GPIO_CFGLR_MODE3 | GPIO_CFGLR_MODE4;
    GPIOD->CFGLR &= ~(GPIO_CFGLR_CNF3| GPIO_CFGLR_CNF4);
    // C0 T2CH3
    GPIOC->CFGLR |= GPIO_CFGLR_MODE0;
    GPIOC->CFGLR &= ~(GPIO_CFGLR_CNF0);
    // D7 T2CH4
    GPIOD->CFGLR |= GPIO_CFGLR_MODE7;
    GPIOD->CFGLR &= ~(GPIO_CFGLR_CNF7);

    // grounds
    // A2
    GPIOA->CFGLR |= GPIO_CFGLR_MODE2;
    GPIOA->CFGLR &= ~GPIO_CFGLR_CNF2;
    // C1
    // C2
    // C5
    // C6
    // C7
    GPIOC->CFGLR |=   GPIO_CFGLR_MODE1 | GPIO_CFGLR_MODE2 | GPIO_CFGLR_MODE5 |  GPIO_CFGLR_MODE6 | GPIO_CFGLR_MODE7;
    GPIOC->CFGLR &= ~(GPIO_CFGLR_CNF1  | GPIO_CFGLR_CNF2  | GPIO_CFGLR_CNF5  | GPIO_CFGLR_CNF6   | GPIO_CFGLR_CNF7);
    // D0
    // D1
    GPIOD->CFGLR |= GPIO_CFGLR_MODE0 | GPIO_CFGLR_MODE1;
    GPIOD->CFGLR &= ~(GPIO_CFGLR_CNF0| GPIO_CFGLR_CNF1);
}

void render_loop(const wchar_t* str, const size_t str_cap)
{
    // find indexes   
    size_t str_len = wcslen(str);
    if(str_len >= str_cap)
    {
        str_len = str_cap - 1;
    }

    size_t str_indexes[str_cap];
    if(str_len == 0)
    {
        str_indexes[0] = glyph_index_or_space(L' ');
        str_len = 1;
    }

    for(size_t i = 0; i < str_len; ++i)
    {
        str_indexes[i] = glyph_index_or_space(str[i]);
    }
    
    
    while(1)
    {
        // sign delay
        static size_t sign_index = 0;
        for(size_t d=0; d < 1000; d++)
        {
            for(size_t i = 0; i<8; i++)
            {
                // 1. precompute masks for active lines
                uint32_t amask=GPIOA_SET_MASK, cmask=GPIOC_SET_MASK, dmask=GPIOD_SET_MASK;

                for(size_t j = 0; j<8; j++)
                {
                    uint8_t current_bit = !!(FONT_8x8[str_indexes[sign_index]].columns[i] & (1<<j));
                    switch(ones[j].gpio_base){
                        case GPIOA_BASE:
                            amask |= ones[j].bitmask*current_bit;
                            break;
                        case GPIOC_BASE:
                            cmask |= ones[j].bitmask*current_bit;
                            break;
                        case GPIOD_BASE:
                            dmask |= ones[j].bitmask*current_bit;
                            break;
                        default:
                        {
                            printf("Fatal Error\r\n"); 
                            while(1);
                        }
                    }
                }
                // 2. switch off last column
                ((GPIO_TypeDef*)(zeros[(i-1)&0x7].gpio_base))->OUTDR |= zeros[(i-1)&0x7].bitmask;

                // 3. reset all and then turn on lines with precomputed masks
                MODIFY_REG(GPIOA->OUTDR, GPIOA_CLEAR_MASK, amask); 
                MODIFY_REG(GPIOC->OUTDR, GPIOC_CLEAR_MASK, cmask); 
                MODIFY_REG(GPIOD->OUTDR, GPIOD_CLEAR_MASK, dmask); 

                // TODO: ghousting in the last row? understand why
                // 4. switch on current column
                ((GPIO_TypeDef*)(zeros[i].gpio_base))->OUTDR &= ~(zeros[i].bitmask);
            }
        }
        //change character
        sign_index++;
        if(sign_index >= str_len)
        {
            sign_index = 0;
        }
        printf("Index znaku %zu \r\n", sign_index);
    }
}

void render_loop_shifting(const wchar_t* str, const size_t str_cap)
{
    size_t str_len = wcslen(str); // bajty?
    if(str_len >= str_cap) // jeśli więcej bajtów niż znaków ???
    {
        str_len = str_cap - 1;
    }

    size_t str_indexes[str_cap];
    if(str_len == 0)
    {
        str_indexes[0] = glyph_index_or_space(L' ');
        str_len = 1;
    }

    for(size_t i = 0; i < str_len; ++i)
    {
        str_indexes[i] = glyph_index_or_space(str[i]);
    }
    
    uint8_t current_frame[8];
    for(size_t i=0; i<8; i++)
    {
        current_frame[i] = FONT_8x8[str_indexes[0]].columns[i];
    }
    while(1)
    {
        static uint32_t col_counter = 0;      
        
        for(size_t d=0; d < 250; d++)
        {
            for(size_t i = 0; i<8; i++)
            {
                // 1. precompute masks for active lines
                uint32_t amask=GPIOA_SET_MASK, cmask=GPIOC_SET_MASK, dmask=GPIOD_SET_MASK;

                for(size_t j = 0; j<8; j++)
                {
                    uint8_t current_bit = !!(current_frame[i] & (1<<j));
                    switch(ones[j].gpio_base){
                        case GPIOA_BASE:
                            amask |= ones[j].bitmask*current_bit;
                            break;
                        case GPIOC_BASE:
                            cmask |= ones[j].bitmask*current_bit;
                            break;
                        case GPIOD_BASE:
                            dmask |= ones[j].bitmask*current_bit;
                            break;
                        default:
                        {
                            printf("Fatal Error\r\n"); 
                            while(1);
                        }
                    }
                }
                // 2. switch off last column
                ((GPIO_TypeDef*)(zeros[(i-1)&0x7].gpio_base))->OUTDR |= zeros[(i-1)&0x7].bitmask;

                // 3. reset all and then turn on lines with precomputed masks
                MODIFY_REG(GPIOD->OUTDR, GPIOD_CLEAR_MASK, dmask);
                MODIFY_REG(GPIOC->OUTDR, GPIOC_CLEAR_MASK, cmask);
                MODIFY_REG(GPIOA->OUTDR, GPIOA_CLEAR_MASK, amask); 
                
                

                // TODO: ghousting in the last row? understand why
                // 4. switch on current column
                ((GPIO_TypeDef*)(zeros[i].gpio_base))->OUTDR &= ~(zeros[i].bitmask);
            }
        }

        //render new frame
        col_counter++;

        //  TODO: logika ku zapobieżeniu overflow
        
        uint32_t current_char_index = col_counter/8;
        uint32_t first_column_index_within_char = col_counter % 8;

        if(current_char_index == str_len-1)
            col_counter = 0;

        uint32_t local_column_count = 0;
        for(size_t i=first_column_index_within_char; i<8; i++, local_column_count++)
        {
           current_frame[local_column_count] = FONT_8x8[str_indexes[current_char_index]].columns[i];
        }  

        if(current_char_index+1 != str_len-1)
        {
            for(size_t i=0; i<8-local_column_count; i++)
            {
                current_frame[local_column_count+i] = FONT_8x8[str_indexes[current_char_index+1]].columns[i];
            }
        }
        else
        {
            for(size_t i=0; i<8-local_column_count; i++)
            {
                current_frame[local_column_count+i] = 0;
            }
        }
    }
}
