/* Owned static-analysis fixture; compiling/inspecting it never requires execution. */
#include <stdio.h>

volatile int rea_bias = 7;

__attribute__((noinline)) int rea_leaf(int value) {
  puts("PI_RE_REA_SENTINEL");
  return value * 3 + rea_bias;
}

__attribute__((noinline)) int rea_branch(int value) {
  if (value > 10)
    return rea_leaf(value) + 1;
  return rea_leaf(value) - 1;
}

int main(void) { return rea_branch(12); }
