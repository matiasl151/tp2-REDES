import config
import threading
import time
import udt
import util


# Go-Back-N protocol.
class GoBackN:

  NO_PREV_ACK_MSG = "Don't have previous ACK to send, will wait for server to timeout."

  # "msg_handler" es utilizado para enviar mensajes a la capa de aplicacion
  def __init__(self, local_port, remote_port, msg_handler):
    util.log("Starting up `Go Back N` protocol ... ")
    self.network_layer = udt.NetworkLayer(local_port, remote_port, self)
    self.msg_handler = msg_handler
    self.sender_base = 0
    self.next_sequence_number = 0
    self.set_timer()
    self.window = [b'']*config.WINDOW_SIZE
    self.expected_sequence_number = 0
    self.receiver_last_ack = b''
    self.is_receiver = True
    self.sender_lock = threading.Lock()


  def set_timer(self):
    self.timer = threading.Timer((config.TIMEOUT_MSEC/1000.0), self._timeout)


  # "send" es llamada por la aplicacion. Devuelve true si es exitoso, false caso contrario.
  def send(self, msg):
    self.is_receiver = False
    if self.next_sequence_number < (self.sender_base + config.WINDOW_SIZE):
      threading.Thread(target=self._send_helper(msg))
      return True
    else:
      util.log("Window is full. App data rejected.")
      time.sleep(1)
      return False


  # Helper ayuda al hilo a mandar el proximo paquete
  def _send_helper(self, msg):
    self.sender_lock.acquire()
    packet = util.make_packet(msg, config.MSG_TYPE_DATA, self.next_sequence_number) # LLamo a la funcion para armar el paquete en util
    packet_data = util.extract_data(packet) # LLamo a la funcion para extraer los datos y recibir el RDTPacket
    self.window[self.next_sequence_number%config.WINDOW_SIZE] = packet
    util.log("Sending data: " + util.pkt_to_string(packet_data))
    self.network_layer.send(packet) #Llama a la funcion para enviar el paquete
    if self.sender_base == self.next_sequence_number:
      if self.timer.is_alive(): self.timer.cancel()
      self.set_timer()
      self.timer.start()
    self.next_sequence_number += 1
    self.sender_lock.release()
    return


  # "handler" es llamado por la capa de red cuando el paquete está listo.
  def handle_arrival_msg(self):
    msg = self.network_layer.recv()
    msg_data = util.extract_data(msg)

    if(msg_data.is_corrupt):
      if(self.is_receiver):
        if self.expected_sequence_number == 0:
          util.log("Packet received is corrupted. " + self.NO_PREV_ACK_MSG)
          return
        self.network_layer.send(self.receiver_last_ack)
        util.log("Received corrupted data. Resending ACK: "
                 + util.pkt_to_string(util.extract_data(self.receiver_last_ack)))
      return

    # Si es un mensaje ACK message, se asume que es para el emisor.
    if msg_data.msg_type == config.MSG_TYPE_ACK:
      self.sender_lock.acquire()
      self.sender_base = msg_data.seq_num + 1
      if(self.sender_base == self.next_sequence_number):
        util.log("Received ACK with seq # matching the end of the window: "
                 + util.pkt_to_string(msg_data) + ". Cancelling timer.")
        self.timer.cancel()
      else:
        util.log("Received ACK: " + util.pkt_to_string(msg_data)
                 + ". There are messages in-flight. Restarting the timer.")
        if self.timer.is_alive(): self.timer.cancel()
        self.set_timer()
        self.timer.start()
      self.sender_lock.release()
    # Si es un mensaje DATA,se asume que es para el receptor
    else:
      assert msg_data.msg_type == config.MSG_TYPE_DATA
      util.log("Received DATA: " + util.pkt_to_string(msg_data))
      if msg_data.seq_num == self.expected_sequence_number:
        self.msg_handler(msg_data.payload)
        ack_pkt = util.make_packet(b'', config.MSG_TYPE_ACK, self.expected_sequence_number)
        self.network_layer.send(ack_pkt)
        self.receiver_last_ack = ack_pkt
        self.expected_sequence_number += 1
        util.log("Sent ACK: " + util.pkt_to_string(util.extract_data(ack_pkt)))
      else:
        if self.expected_sequence_number == 0:
          util.log("Packet received is out of order. " + self.NO_PREV_ACK_MSG)
          return
        util.log("DATA message had unexpected sequence #"
                 + str(int(msg_data.seq_num)) + ". Resending ACK message with sequence # "
                 + str(int(self.expected_sequence_number-1)) + ".")
        self.network_layer.send(self.receiver_last_ack)
    return


  # Limpia los recursos.
  def shutdown(self):
    if not self.is_receiver: self._wait_for_last_ACK()
    if self.timer.is_alive(): self.timer.cancel()
    util.log("Connection shutting down...")
    self.network_layer.shutdown()


  def _wait_for_last_ACK(self):
    while self.sender_base < self.next_sequence_number-1:
      util.log("Waiting for last ACK from receiver with sequence # "
               + str(int(self.next_sequence_number-1)) + ".")
      time.sleep(1)


  def _timeout(self):
    util.log("Timeout! Resending all packets in window. Resending packets with seq #s "
             + str(self.sender_base) + "-" + str(self.next_sequence_number-1) +".")
    self.sender_lock.acquire()
    if self.timer.is_alive(): self.timer.cancel()
    self.set_timer()
    for i in range(self.sender_base,self.next_sequence_number):
      pkt = self.window[(i%config.WINDOW_SIZE)]
      self.network_layer.send(pkt)
      util.log("Resending packet: " + util.pkt_to_string(util.extract_data(pkt)))
    self.timer.start()
    self.sender_lock.release()
    return