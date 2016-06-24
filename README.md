# Retro Language

This is the start of a port of Retro to the Nga virtual machine. Nga is the
next generation of the Ngaro VM. Nga has a simpler instruction set, smaller
implementation, and richer toolchain. But Nga doesn't have an I/O model. This
branch of development brings the classic Ngaro-style I/O to Nga.

Using the Nga toolchain this also includes the start of a new Retro kernel.
The hope is that this will smooth the migration to a new VM and minimize the
impact on existing applications.
