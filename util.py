import dummy
import gbn
import ss
import struct
import time

SIXTEEN_BIT_MASK = 0xffff

      ##################################################################################################################
      # Esta clase engloba varias piezas de información incluidas en un segmento la capa de transporte que incluye     #
      # el tipo de mensaje (ACK o DATA), el número de secuencia, el valor checksum, y el mensaje.                      #
      # También contiene una bandera booleana que indica la corrupción de datos.                                       #
      ##################################################################################################################

class RDTPacket:
  def __init__(self, msg_type, seq_num, checksum, payload, is_corrupt):
    self.msg_type = msg_type
    self.seq_num = seq_num
    self.checksum = checksum
    self.payload = payload
    self.is_corrupt = is_corrupt

#Representación de flag indicando paquete corrupto
def get_corrupt_packet_representation():
  return RDTPacket(None, None, None, None, True)


####################################################

#Función para obtener el checksum
def get_checksum(pkt):
  checksum = 0
  byte_list = list(pkt[i:i+2] for i in range(0, len(pkt), 2))
  for chunk in byte_list:
    num = struct.unpack('!H', chunk)[0] if len(chunk) == 2 else struct.unpack('!B', chunk)[0]
    checksum += num
  # fold the carry so the checksum is 16 bits long
  checksum = (checksum >> 16) + (checksum & SIXTEEN_BIT_MASK)
  return checksum ^ SIXTEEN_BIT_MASK   # get one's complement

#Función que arma el paquete
def make_packet(msg, type, seq_num):
  bytelist = []
  bytelist.append(struct.pack('!H', type))     # HEADER 1: Tipo de mensaje
  bytelist.append(struct.pack('!H', seq_num))  # HEADER 2: Numero de secuencia
  bytelist.append(struct.pack('!H', 0))        # HEADER 3: CHECKSUM (append 0 for now)
  bytelist.append(msg)                         # El mensaje

  checksum = get_checksum(b''.join(bytelist))
  checksum_bytes = struct.pack("!H", checksum)
  assert len(checksum_bytes) == 2

  bytelist[2] = checksum_bytes
  packet = b''.join(bytelist)
  return packet

#Funión para extraer los datos
def extract_data(msg):
  if len(msg) < 6 or not get_checksum(msg) == 0:
    return get_corrupt_packet_representation()
  headers = struct.unpack("!3H", msg[0:6])
  return RDTPacket(headers[0], headers[1], headers[2], msg[6:], False) # Arma el RDTPacket

#To string de Packet_data
def pkt_to_string(pkt):
  type = "type: " + ("ACK" if pkt.msg_type == 2 else "DATA")
  seq_num = "seq#: " + str(pkt.seq_num)
  payload = ""
  if(pkt.payload):
    payload = ", payload: " + str(pkt.payload)[:20]
    if len(pkt.payload) > 20: payload += "..."
  return " [" + type + ", " + seq_num + payload + "]"

#Funión para obtener la capa de transporte por su nombre
def get_transport_layer_by_name(name, local_port, remote_port, msg_handler):
  assert name == 'dummy' or name == 'ss' or name == 'gbn'
  if name == 'dummy':
    return dummy.DummyTransportLayer(local_port, remote_port, msg_handler)
  if name == 'ss':
    return ss.StopAndWait(local_port, remote_port, msg_handler)
  if name == 'gbn':
    return gbn.GoBackN(local_port, remote_port, msg_handler)


def now():
  return time.strftime("[%a %m-%d-%y %H:%M:%S] ")


def log(msg):
  print(now() + msg)
