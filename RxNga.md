````
/* Ngaro VM ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   Copyright (c) 2008 - 2011, Charles Childers
   Copyright (c) 2009 - 2010, Luke Parrish
   Copyright (c) 2010,        Marc Simpson
   Copyright (c) 2010,        Jay Skeer
   Copyright (c) 2011,        Kenneth Keating
   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include <string.h>
#include <termios.h>
#include <sys/ioctl.h>
/* ATH */
#include <sys/stat.h>
#include <errno.h>

#include "nga.c"

#define PORTS                12
#define MAX_FILE_NAME      1024
#define MAX_REQUEST_LENGTH 1024
#define MAX_OPEN_FILES        8
#define CELLSIZE             32

typedef struct {
  CELL ports[PORTS];
  FILE *files[MAX_OPEN_FILES];
  FILE *input[MAX_OPEN_FILES];
  CELL isp;
  char filename[MAX_FILE_NAME];
  char request[MAX_REQUEST_LENGTH];
  struct termios new_termios, old_termios;
} VM;

/* Macros ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */

/* Helper Functions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
void rxGetString(VM *vm, int starting)
{
  CELL i = 0;
  while(memory[starting] && i < MAX_REQUEST_LENGTH)
    vm->request[i++] = (char)memory[starting++];
  vm->request[i] = 0;
}

/* Console I/O Support ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
void rxWriteConsole(CELL c) {
  (c > 0) ? putchar((char)c) : printf("\033[2J\033[1;1H");
  /* Erase the previous character if c = backspace */
  if (c == 8) {
    putchar(32);
    putchar(8);
  }
}

CELL rxReadConsole(VM *vm) {
  CELL c;
  if ((c = getc(vm->input[vm->isp])) == EOF && vm->input[vm->isp] != stdin) {
    fclose(vm->input[vm->isp--]);
    c = 0;
  }
  if (c == EOF && vm->input[vm->isp] == stdin)
    exit(0);
  return c;
}

void rxIncludeFile(VM *vm, char *s) {
  FILE *file;
  if ((file = fopen(s, "r")))
    vm->input[++vm->isp] = file;
}

void rxPrepareInput(VM *vm) {
  vm->isp = 0;
  vm->input[vm->isp] = stdin;
}

void rxPrepareOutput(VM *vm) {
  tcgetattr(0, &vm->old_termios);
  vm->new_termios = vm->old_termios;
  vm->new_termios.c_iflag &= ~(BRKINT+ISTRIP+IXON+IXOFF);
  vm->new_termios.c_iflag |= (IGNBRK+IGNPAR);
  vm->new_termios.c_lflag &= ~(ICANON+ISIG+IEXTEN+ECHO);
  vm->new_termios.c_cc[VMIN] = 1;
  vm->new_termios.c_cc[VTIME] = 0;
  tcsetattr(0, TCSANOW, &vm->new_termios);
}

void rxRestoreIO(VM *vm) {
  tcsetattr(0, TCSANOW, &vm->old_termios);
}

/* File I/O Support ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
CELL rxGetFileHandle(VM *vm)
{
  CELL i;
  for(i = 1; i < MAX_OPEN_FILES; i++)
    if (vm->files[i] == 0)
      return i;
  return 0;
}

void rxAddInputSource(VM *vm) {
  CELL name = TOS; sp--;
  rxGetString(vm, name);
  rxIncludeFile(vm, vm->request);
}

CELL rxOpenFile(VM *vm) {
  CELL slot, mode, name;
  slot = rxGetFileHandle(vm);
  mode = TOS; sp--;
  name = TOS; sp--;
  rxGetString(vm, name);
  if (slot > 0)
  {
    if (mode == 0)  vm->files[slot] = fopen(vm->request, "r");
    if (mode == 1)  vm->files[slot] = fopen(vm->request, "w");
    if (mode == 2)  vm->files[slot] = fopen(vm->request, "a");
    if (mode == 3)  vm->files[slot] = fopen(vm->request, "r+");
  }
  if (vm->files[slot] == NULL)
  {
    vm->files[slot] = 0;
    slot = 0;
  }
  return slot;
}

CELL rxReadFile(VM *vm) {
  CELL c = fgetc(vm->files[TOS]); sp--;
  return (c == EOF) ? 0 : c;
}

CELL rxWriteFile(VM *vm) {
  CELL slot, c, r;
  slot = TOS; sp--;
  c = TOS; sp--;
  r = fputc(c, vm->files[slot]);
  return (r == EOF) ? 0 : 1;
}

CELL rxCloseFile(VM *vm) {
  fclose(vm->files[TOS]);
  vm->files[TOS] = 0;
  sp--;
  return 0;
}

CELL rxGetFilePosition(VM *vm) {
  CELL slot = TOS; sp--;
  return (CELL) ftell(vm->files[slot]);
}

CELL rxSetFilePosition(VM *vm) {
  CELL slot, pos, r;
  slot = TOS; sp--;
  pos  = TOS; sp--;
  r = fseek(vm->files[slot], pos, SEEK_SET);
  return r;
}

CELL rxGetFileSize(VM *vm) {
  CELL slot, current, r, size;
  slot = TOS; sp--;
  current = ftell(vm->files[slot]);
  r = fseek(vm->files[slot], 0, SEEK_END);
  size = ftell(vm->files[slot]);
  fseek(vm->files[slot], current, SEEK_SET);
  return (r == 0) ? size : 0;
}

CELL rxDeleteFile(VM *vm) {
  CELL name = TOS; sp--;
  rxGetString(vm, name);
  return (unlink(vm->request) == 0) ? -1 : 0;
}

CELL rxLoadImage(VM *vm, char *image) {
}

CELL rxSaveImage(VM *vm, char *image) {
}

/* Environment Query ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
void rxQueryEnvironment(VM *vm) {
  CELL req, dest;
  char *r;
  req = TOS;  sp--;
  dest = TOS; sp--;

  rxGetString(vm, req);
  r = getenv(vm->request);

  if (r != 0)
    while (*r != '\0')
    {
      memory[dest] = *r;
      dest++;
      memory[dest] = 0;
      r++;
    }
  else
    memory[dest] = 0;
}

/* Device I/O Handler ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
void rxDeviceHandler(VM *vm) {
  struct winsize w;
  if (vm->ports[0] != 1) {
    /* Input */
    if (vm->ports[0] == 0 && vm->ports[1] == 1) {
      vm->ports[1] = rxReadConsole(vm);
      vm->ports[0] = 1;
    }

    /* Output (character generator) */
    if (vm->ports[2] == 1) {
      rxWriteConsole(TOS); sp--;
      vm->ports[2] = 0;
      vm->ports[0] = 1;
    }

    /* File IO and Image Saving */
    if (vm->ports[4] != 0) {
      vm->ports[0] = 1;
      switch (vm->ports[4]) {
        case  1: rxSaveImage(vm, vm->filename);
                 vm->ports[4] = 0;
                 break;
        case  2: rxAddInputSource(vm);
                 vm->ports[4] = 0;
                 break;
        case -1: vm->ports[4] = rxOpenFile(vm);
                 break;
        case -2: vm->ports[4] = rxReadFile(vm);
                 break;
        case -3: vm->ports[4] = rxWriteFile(vm);
                 break;
        case -4: vm->ports[4] = rxCloseFile(vm);
                 break;
        case -5: vm->ports[4] = rxGetFilePosition(vm);
                 break;
        case -6: vm->ports[4] = rxSetFilePosition(vm);
                 break;
        case -7: vm->ports[4] = rxGetFileSize(vm);
                 break;
        case -8: vm->ports[4] = rxDeleteFile(vm);
                 break;
        default: vm->ports[4] = 0;
      }
    }

    /* Capabilities */
    if (vm->ports[5] != 0) {
      vm->ports[0] = 1;
      switch(vm->ports[5]) {
        case -1:  vm->ports[5] = IMAGE_SIZE;
                  break;
        case -2:  vm->ports[5] = 0;
                  break;
        case -3:  vm->ports[5] = 0;
                  break;
        case -4:  vm->ports[5] = 0;
                  break;
        case -5:  vm->ports[5] = sp;
                  break;
        case -6:  vm->ports[5] = rp;
                  break;
        case -7:  vm->ports[5] = 0;
                  break;
        case -8:  vm->ports[5] = time(NULL);
                  break;
        case -9:  vm->ports[5] = 0;
                  ip = IMAGE_SIZE;
                  break;
        case -10: vm->ports[5] = 0;
                  rxQueryEnvironment(vm);
                  break;
        case -11: ioctl(0, TIOCGWINSZ, &w);
                  vm->ports[5] = w.ws_col;
                  break;
        case -12: ioctl(0, TIOCGWINSZ, &w);
                  vm->ports[5] = w.ws_row;
                  break;
        case -13: vm->ports[5] = CELLSIZE;
                  break;
        case -14: vm->ports[5] = 0;
                  break;
        case -15: vm->ports[5] = -1;
                  break;
        case -16: vm->ports[5] = STACK_DEPTH;
                  break;
        case -17: vm->ports[5] = ADDRESSES;
                  break;
        default:  vm->ports[5] = 0;
      }
    }

    if (vm->ports[8] != 0) {
      switch (vm->ports[8]) {
        case 1: vm->ports[8] = 0;
                printf("\e[%d;%dH", NOS, TOS);
                sp--; sp--;
                break;
        case 2: vm->ports[8] = 0;
                printf("\e[3%dm", TOS);
                sp--;
                break;
        case 3: vm->ports[8] = 0;
                printf("\e[4%dm", TOS);
                sp--;
                break;
        case 4: vm->ports[8] = 0;
                break;
        default: vm->ports[8] = 0;
      }
    }
  }
}




void processOpcodes(VM *vm) {
  CELL opcode;
  CELL a;
  ip = 0;
  while (ip < IMAGE_SIZE) {
    opcode = memory[ip];
    if (opcode >= 0 && opcode < 27)
      ngaProcessOpcode();
    else
      switch(opcode) {
        case 90:
          a = TOS;
          TOS = vm->ports[a];
          vm->ports[a] = 0;
          break;
        case 91:
          vm->ports[TOS] = NOS;
          sp--; sp--;
          break;
        case 92:
          rxDeviceHandler(vm);
          break;
      }
    ip++;
  }
}

/*
*/

/* Main ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
int main(int argc, char **argv) {
  VM *vm;
  int i, wantsStats, dumpAfter;

  /* ATH */
  char *env;
  struct stat sts;

  wantsStats = 0;
  vm = calloc(sizeof(VM), sizeof(char));
  strcpy(vm->filename, "retroImage");

  rxPrepareInput(vm);

  if ( ( stat( vm->filename, &sts) == -1 ) && errno == ENOENT ) {
      // File doesn't exist, get the environment variable.
      env = (char *)getenv("RETROIMAGE");
      if( !env ) {
        fprintf(stderr,"No image file and environment variable RETROIMAGE not set.\n");
        exit(1);
      } else {
          strncpy(vm->filename, env,sizeof(vm->filename));
          fprintf(stderr,"Loading image from %s\n", env);
      }
  }
  if (rxLoadImage(vm, vm->filename) == 0) {
    printf("Sorry, unable to find %s\n", vm->filename);
    free(vm);
    exit(1);
  }

  rxPrepareOutput(vm);
  processOpcodes(vm);
  rxRestoreIO(vm);

  free(vm);
  return 0;
}
````
