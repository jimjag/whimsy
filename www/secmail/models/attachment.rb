class Attachment
  IMAGE_TYPES = %w(.gif, .jpg, .jpeg, .png)
  attr_reader :headers

  def initialize(message, headers, part)
    @message = message
    @headers = headers
    @part = part
  end

  def name
    headers[:name] || @part.filename
  end

  def content_type
    headers[:mime] || @part.content_type
  end

  def body
    headers[:content] || @part.body
  end

  def safe_name
    name = self.name.dup
    name.gsub! /^\W/, ''
    name.gsub! /[^\w.]/, '_'
    name.untaint
  end

  def as_file
    file = Tempfile.new([safe_name, '.pdf'], encoding: Encoding::BINARY)
    file.write(body)
    file.rewind
    file
  end

  def as_pdf
    file = Tempfile.new([safe_name, '.pdf'], encoding: Encoding::BINARY)
    file.write(body)
    file.rewind

    return file if content_type.end_with? '/pdf'
    return file if name.end_with? '.pdf'

    ext = File.extname(name).downcase

    if IMAGE_TYPES.include? ext or content_type.start_with? 'image/'
      pdf = Tempfile.new([safe_name, '.pdf'], encoding: Encoding::BINARY)
      system 'convert', file.path, pdf.path
      file.unlink
      return pdf
    end

    return file
  end

  # write a file out to svn
  def write_svn(repos, file)
    filename = File.join(repos, file)
    filename = File.join(filename, safe_name) if Dir.exist? filename

    raise Errno::EEXIST.new(file) if File.exist? filename
    File.write filename, body, encoding: Encoding::BINARY

    system 'svn', 'add', filename
    system 'svn', 'propset', 'svn:mime-type', content_type.untaint, filename

    filename
  end
end
