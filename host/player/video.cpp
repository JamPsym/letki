#include "player.hpp"
#include <algorithm>
#include <cmath>
#include <deque>
#include <stdexcept>
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libswscale/swscale.h>
}
namespace letki {
struct Video::Impl {
  AVFormatContext *input = nullptr;
  AVCodecContext *codec = nullptr;
  AVFrame *decoded = nullptr;
  AVPacket *packet = nullptr;
  SwsContext *scaler = nullptr;
  int stream = -1;
  double length = 0, start = 0;
  bool drained = false;
  double last = -1;
  struct Cached {
    double time;
    VideoImage image;
  };
  std::deque<Cached> cache;
  ~Impl() {
    sws_freeContext(scaler);
    av_packet_free(&packet);
    av_frame_free(&decoded);
    avcodec_free_context(&codec);
    avformat_close_input(&input);
  }
  void open(const std::string &path) {
    if (avformat_open_input(&input, path.c_str(), nullptr, nullptr) < 0 ||
        avformat_find_stream_info(input, nullptr) < 0)
      throw std::runtime_error("Cannot open video: " + path);
    const AVCodec *decoder = nullptr;
    stream =
        av_find_best_stream(input, AVMEDIA_TYPE_VIDEO, -1, -1, &decoder, 0);
    if (stream < 0)
      throw std::runtime_error("No video stream in " + path);
    codec = avcodec_alloc_context3(decoder);
    if (!codec || avcodec_parameters_to_context(
                      codec, input->streams[stream]->codecpar) < 0)
      throw std::runtime_error("Cannot configure video decoder");
    codec->thread_count = 2;
    if (avcodec_open2(codec, decoder, nullptr) < 0)
      throw std::runtime_error("Cannot start video decoder");
    if (codec->width < 1 || codec->height < 1 || codec->width > 8192 ||
        codec->height > 8192)
      throw std::runtime_error("Video dimensions must be within 8192x8192");
    auto s = input->streams[stream];
    start = s->start_time == AV_NOPTS_VALUE
                ? 0
                : s->start_time * av_q2d(s->time_base);
    length = s->duration != AV_NOPTS_VALUE
                 ? s->duration * av_q2d(s->time_base)
                 : input->duration / double(AV_TIME_BASE);
    if (!std::isfinite(length) || length <= 0)
      throw std::runtime_error("Seekable video needs a known duration");
    decoded = av_frame_alloc();
    packet = av_packet_alloc();
    if (!decoded || !packet)
      throw std::bad_alloc();
  }
  void seek(double t) {
    auto s = input->streams[stream];
    int64_t ts = int64_t((t + start) / av_q2d(s->time_base));
    if (av_seek_frame(input, stream, ts, AVSEEK_FLAG_BACKWARD) < 0)
      throw std::runtime_error("Video seek failed");
    avcodec_flush_buffers(codec);
    av_packet_unref(packet);
    drained = false;
    last = -1;
    cache.clear();
  }
  bool next() {
    for (;;) {
      int r = avcodec_receive_frame(codec, decoded);
      if (r == 0) {
        double time = decoded->best_effort_timestamp == AV_NOPTS_VALUE
                          ? (last < 0 ? 0 : last + 1 / 25.)
                          : decoded->best_effort_timestamp *
                                    av_q2d(input->streams[stream]->time_base) -
                                start;
        double scale =
            std::min({1., 960. / decoded->width, 540. / decoded->height});
        Cached c{};
        c.time = std::max(0., time);
        c.image.width = std::max(1, int(decoded->width * scale));
        c.image.height = std::max(1, int(decoded->height * scale));
        c.image.stride = (c.image.width * 3 + 63) & ~63;
        c.image.rgb.resize(size_t(c.image.stride) * c.image.height + 64);
        scaler = sws_getCachedContext(
            scaler, decoded->width, decoded->height,
            AVPixelFormat(decoded->format), c.image.width, c.image.height,
            AV_PIX_FMT_RGB24, SWS_BILINEAR, nullptr, nullptr, nullptr);
        if (!scaler)
          throw std::runtime_error("Cannot scale PC video");
        uint8_t *dst[] = {c.image.rgb.data(), nullptr, nullptr, nullptr};
        int strides[] = {c.image.stride, 0, 0, 0};
        if (sws_scale(scaler, decoded->data, decoded->linesize, 0,
                      decoded->height, dst, strides) != c.image.height)
          throw std::runtime_error("PC video conversion failed");
        cache.push_back(std::move(c));
        while (cache.size() > 4)
          cache.pop_front();
        last = time;
        av_frame_unref(decoded);
        return true;
      }
      if (r == AVERROR_EOF)
        return false;
      if (r != AVERROR(EAGAIN))
        throw std::runtime_error("Video decoder failed");
      if (drained)
        return false;
      do {
        r = av_read_frame(input, packet);
        if (r < 0) {
          avcodec_send_packet(codec, nullptr);
          drained = true;
          break;
        }
        if (packet->stream_index != stream) {
          av_packet_unref(packet);
          continue;
        }
        int sent = avcodec_send_packet(codec, packet);
        av_packet_unref(packet);
        if (sent < 0)
          throw std::runtime_error("Video packet rejected");
        break;
      } while (true);
    }
  }
  const VideoImage &at(double t) {
    t = std::fmod(std::max(0., t), length);
    if (cache.empty() || t < cache.front().time - .05 ||
        t > cache.back().time + 2)
      seek(t);
    unsigned guard = 0;
    while ((cache.empty() || cache.back().time <= t + 1e-7) && next()) {
      if (++guard > 10000)
        throw std::runtime_error("Video timestamp gap too large");
    }
    if (cache.empty())
      throw std::runtime_error("Video contains no decodable frames");
    auto selected = cache.begin();
    for (auto it = cache.begin(); it != cache.end() && it->time <= t + 1e-7;
         it++)
      selected = it;
    return selected->image;
  }
};
Video::Video(const std::string &path) : p(new Impl) { p->open(path); }
Video::~Video() = default;
double Video::duration() const { return p->length; }
const VideoImage &Video::image(double t) { return p->at(t); }
} // namespace letki
