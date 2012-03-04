import pyglet
from pyglet.gl import *
from vector import Vector
import math

from track import WALL, DEEP, GRASS, ROAD, JUMP, BOOST, FINISH, START, ITEM, EMPTY
from items import ITEMS

from graphics import sprite_seq

class Car(object):
	def __init__(self, race, racer, character, position):
		self.race = race
		self.racer = racer
		self.character = character # the character in the car
		self.position = position
		self.last_ground = position # the last valid position of the car
		self.speed = Vector(0., 0.)
		self.direction = math.pi/2 # direction that the car is facing (angle in radians)
		self.state = CarState(self)
		
		# the sprite of the car
		self.sprite = pyglet.sprite.Sprite(self.choose_sprite(), batch=race.window.batch, group=race.track.cars_group)
		self.shadow = pyglet.sprite.Sprite(sprite_seq[38], batch=race.window.batch, group=race.track.shadows_group)
		self.shadow.opacity = 100
		self.sprite.position = self.position.pair()
	
	def __cmp__(self, other):
		"""compares the relative advancement of two cars. Returns a positive value if self is behind other"""
		if self.racer.lap != other.racer.lap: # first, compare the laps of each car
			return other.racer.lap - self.racer.lap
		b1 = self.race.track.get_beacon_id(self.position)
		if b1 == 255:
			b1 = self.race.track.get_beacon_id(self.last_ground)
		b2 = self.race.track.get_beacon_id(other.position)
		if b2 == 255:
			b2 = self.race.track.get_beacon_id(other.last_ground)
		if b1 != b2: # if equal laps, compare the beacon at which each car is
			return b2 - b1
		beacons = self.race.track.beacons
		beacons_dir = beacons[(b1 + 1) % len(beacons)] - beacons[(b1 - 1) % len(beacons)] # next beacon - previous beacon
		cars_dir = other.position - self.position
		return beacons_dir * cars_dir # if same beacon, scalar product of the vectors to determine which car is in front, according to the direction (vp-vn)

	def choose_sprite(self):
		"""returns the appropriate sprite image index according to the orientation of the car"""
		angle = -(math.pi/2 + self.direction) % (2*math.pi) # translate the angle to correspond to the sprites (0 is up, increasing clockwise)
		return self.character['sprite_seq'][int(round(angle * 11 / math.pi)) % 22] # there are 22 possible orientation sprites
	
	# player inputs
	def turn(self, dt):
		"""turn the car after dt seconds (positive: turn left, negative: turn right)"""
		self.set_direction(self.get_direction() + self.character['turn'] * dt)
	def jump(self):
		"""the car makes a low jump"""
		if not self.state.jump and not self.state.aerial:
			self.state.change(jump=0.25)
	def lakitu(self):
		"""the car must be put back on the track by Lakitu"""
		self.set_position(self.race.track.get_beacon(self.last_ground)) # move the car to the nearest beacon
		self.racer.state.active = False
		self.stop()
		self.state.change(lakitu = 1.) # timer until the car is dropped on the track
		track = self.race.track
		self.lakitu_sprite = pyglet.sprite.Sprite(sprite_seq[37], batch=self.race.window.batch, group=track.cars_group)
		self.lakitu_sprite.opacity = 0
		self.lakitu_sprite.position = self.position.pair()
		# reorient the car
		bid = track.get_beacon_id(self.position)
		direction_vector = track.beacons[(bid+1)%len(track.beacons)] - track.beacons[bid-1]
		self.set_direction(direction_vector.angle())

	def mass(self):
		"""returns the mass of the car"""
		if self.state.lightning:
			return self.character['mass']/2
		else:
			return self.character['mass']
	def is_vulnerable(self):
		"""test whether the car can be harmed"""
		if self.state.lakitu or self.state.star:
			return False
		else:
			return True
	def get_radius(self):
		"""returns the current radius of the car"""
		if self.state.lightning:
			return self.character['radius']/2
		else:
			return self.character['radius']
	def set_position(self, new_position):
		"""change the current position of the car"""
		# check if the finish line was passed
		x1, x2, y = self.race.track.finish_line
		if x1 <= new_position.x <= x2:
			if self.position.y < y and new_position.y >= y:
				self.racer.new_lap() # line was passed
			elif self.position.y >= y and new_position.y < y:
				self.racer.new_lap(-1) # line was passed backwards
		self.position = new_position
		# position the sprite according to the state of the car
		self.shadow.position = self.position.pair()
		if self.state.jump:
			self.sprite.position = (self.position + Vector(0, 5)).pair()
		elif self.state.aerial:
			self.sprite.position = (self.position + Vector(0, 10)).pair()
		else:
			self.sprite.position = self.position.pair()
			self.last_ground = self.position

	def move(self, new_position):
		"""move the car"""
		if not self.state.aerial: # a flying car can move over anything
			if self.race.track.type(new_position) == WALL:
			# hit a wall
				self.set_speed(-.25*self.speed) # bounce
				new_position = self.position # do not move
			if not self.state.jump:
				if self.race.track.type(new_position) in [WALL, DEEP]:
				# car is in an invalid position
					return self.lakitu()
				if self.racer.item == ITEMS[0] and self.race.track.type(new_position, special=True) == ITEM:
				# the car touched an item block
					block = self.race.track.item_blocks[(int(new_position.x)/8, int(new_position.y)/8)] # find the block that was touched
					if not block.delay:
						block.activate()
						self.racer.get_item()
				if self.race.track.type(new_position) == JUMP:
				# touch a bumper
					if self.speed.norm() < 100:
						self.set_speed(self.speed.normalize(100.))
					self.state.change(aerial=.5)
				if self.race.track.type(new_position) == BOOST and self.speed.norm() < 300.:
				# touch a booster
					self.set_speed(self.speed.normalize(300.))
		self.set_position(new_position)
	
	def stop(self):
		"""stops the car by killing its speed"""
		self.set_speed(Vector(0., 0.))
	def set_speed(self, new_speed):
		"""changes the speed of the car"""
		self.speed = new_speed
	def get_direction(self):
		"""returns the current orientation of the car (in radians)"""
		return self.direction
	def get_direction_vector(self):
		"""returns the orientation of the car as a unit vector"""
		return Vector(math.cos(self.direction), math.sin(self.direction))
	def set_direction(self, new_direction):
		"""changes the orientation of the car"""
		self.direction = new_direction % (2*math.pi)
		self.sprite.image = self.choose_sprite() # update the sprite of the car
	
	def update(self, dt):
		"""make the car move after dt seconds"""
		mass = self.mass()
		direction_vector = self.get_direction_vector()
		left_vector = Vector(-direction_vector.y, direction_vector.x) # orthogonal direction
		speed_vector = self.speed
		speed_norm = self.speed.norm()
		u_speed = speed_vector.normalize(1.)
		
		# read inputs:
		acc = Vector(0., 0.)
		brake = False
		if self.racer.state.active:
			if self.racer.input_left:
				self.turn(dt)
			elif self.racer.input_right:
				self.turn(-dt)
			if self.racer.input_accelerate:
				acc += direction_vector.normalize(self.character['acceleration']) * dt / mass
			if self.racer.input_brake:
				acc -= direction_vector.normalize(self.character['acceleration']) * dt / mass / 2
		
		# ** fluid friction
		ff = -self.character['friction'] * speed_vector * dt / mass
		
		# ** solid friction (parallel and orthogonal are computed separately)
		# parallel solid friction
		psf_coef = self.race.track.ground_friction(self.position) * dt / mass
		if psf_coef > speed_norm:
			psf_coef = speed_norm
		psf = -psf_coef * (u_speed * direction_vector) * direction_vector
		# orthogonal solid friction
		osf_coef = (self.character['adhesion'] + self.race.track.ground_friction(self.position)) * dt / mass
		if osf_coef > speed_norm:
			osf_coef = speed_norm
		osf = -osf_coef * (u_speed * left_vector) * left_vector
		
		self.set_speed(self.speed + acc + ff + psf + osf)
		self.move(self.position + self.speed * dt)
		self.state.update(dt)


class CarState(object):
	"""The current state of a car"""
	def __init__(self, car):
		self.car = car
		self.jump = 0. # car is jumping
		self.mushroom = 0. # player has used a mushroom
		self.star = 0. # car is under the effect of a power star (remaining time)
		self.coins = 0 # number of coins
		self.aerial = 0. # car is flying
		self.lightning = 0. # car has been affected by a lightning (remaining time)
		self.lakitu = 0. # if the car is being rescued by Lakitu (fallen in deep ground)
	
	def change(self, lightning=None, jump=None, aerial=None, mushroom=None, lakitu=None):
		"""changes the state of the car, in a way that enables to fix the different parameters that are affected"""
		if lightning != None:
			self.lightning = lightning
			if lightning > 0:
				self.car.sprite.scale = .5
				self.car.shadow.scale = .5
		if jump != None: # regular jump
			self.jump = jump
		if aerial != None: # super jump (feather or bumper)
			self.aerial = aerial
		if mushroom != None:
			self.mushroom = mushroom
		if lakitu != None:
			self.lakitu = lakitu
	
	def update(self, dt):
		"""updates the state of a car after dt seconds"""
		if self.mushroom:
			self.mushroom = max(0., self.mushroom - dt)
		if self.jump:
			self.jump = max(0., self.jump - dt)
		if self.aerial:
			self.aerial = max(0., self.aerial - dt)
		if self.star:
			self.star = max(0., self.star - dt)
		if self.lightning:
			self.lightning = max(0., self.lightning - dt)
			if not self.lightning:
				self.car.sprite.scale = 1
				self.car.shadow.scale = 1
		if self.lakitu:
			self.lakitu = max(0., self.lakitu - dt/2)
			opacity = 255 - int(self.lakitu*255)
			self.car.lakitu_sprite.opacity = opacity
			self.car.sprite.opacity = opacity
			if not self.lakitu:
				self.car.lakitu_sprite.delete()
				self.car.racer.state.active = True