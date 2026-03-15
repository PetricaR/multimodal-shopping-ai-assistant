export class PCMStreamPlayer {
  private audioContext: AudioContext;
  private nextStartTime: number = 0;
  private scheduledSources: Set<AudioBufferSourceNode> = new Set();
  private sampleRate: number;

  constructor(audioContext: AudioContext, sampleRate: number = 24000) {
    this.audioContext = audioContext;
    this.sampleRate = sampleRate;
  }

  async playChunk(base64Data: string) {
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }

    const pcmData = AudioUtils.base64Decode(base64Data);
    const audioBuffer = AudioUtils.pcmToAudioBuffer(pcmData, this.audioContext, this.sampleRate);

    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);

    const currentTime = this.audioContext.currentTime;
    if (this.nextStartTime < currentTime) {
      this.nextStartTime = currentTime;
    }

    source.start(this.nextStartTime);
    this.nextStartTime += audioBuffer.duration;
    this.scheduledSources.add(source);

    source.onended = () => {
      this.scheduledSources.delete(source);
    };
  }

  stop() {
    this.scheduledSources.forEach(source => {
      try { source.stop(); } catch (e) { }
    });
    this.scheduledSources.clear();
    this.nextStartTime = 0;
  }

  get isPlaying() {
    return this.scheduledSources.size > 0;
  }
}

export const AudioUtils = {
  /**
   * Simple linear resample
   */
  resample: (data: Float32Array, inputRate: number, outputRate: number): Float32Array => {
    if (inputRate === outputRate) return data;
    const ratio = inputRate / outputRate;
    const newLength = Math.round(data.length / ratio);
    const result = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
      const index = Math.floor(i * ratio);
      result[i] = data[index];
    }
    return result;
  },

  /**
   * Convert Float32Array to PCM Int16 ArrayBuffer
   */
  floatTo16BitPCM: (float32Array: Float32Array): ArrayBuffer => {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buffer;
  },

  /**
   * Encode Uint8Array to Base64 string
   */
  base64Encode: (bytes: Uint8Array): string => {
    let binary = '';
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  },

  /**
   * Decode Base64 string to Uint8Array
   */
  base64Decode: (base64: string): Uint8Array => {
    const binaryString = atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes;
  },

  /**
   * Decode PCM raw data into an AudioBuffer
   */
  pcmToAudioBuffer: (
    pcmData: Uint8Array,
    audioContext: AudioContext,
    sampleRate: number = 24000
  ): AudioBuffer => {
    const dataInt16 = new Int16Array(pcmData.buffer);
    const frameCount = dataInt16.length;
    const buffer = audioContext.createBuffer(1, frameCount, sampleRate);
    const channelData = buffer.getChannelData(0);

    for (let i = 0; i < frameCount; i++) {
      channelData[i] = dataInt16[i] / 32768.0;
    }
    return buffer;
  }
};