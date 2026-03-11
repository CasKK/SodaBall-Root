import pygame
from pygame._sdl2.video import Window

pygame.init()

print("Displays:", pygame.display.get_desktop_sizes())
help(Window)
# Window on monitor 0
win1 = Window("Left", size=(800,600), display=0)
win1.position = (100, 100)

# Window on monitor 1
win2 = Window("Right", size=(800,600), display=1)
win2.position = (100, 100)

running = True
clock = pygame.time.Clock()

while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

    win1.get_surface().fill((255,0,0))
    win2.get_surface().fill((0,0,255))

    win1.flip()
    win2.flip()
    clock.tick(60)

pygame.quit()