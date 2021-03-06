#!/usr/bin/env ruby

$LOAD_PATH.unshift File.realpath(File.expand_path('../../../lib', __FILE__))

#
# SVN Repository status
#

require 'yaml'
require 'wunderbar/bootstrap'
require 'whimsy/asf'

# load list of repositories
repository_file = File.expand_path('../../../repository.yml', __FILE__)
repository = YAML.load_file(repository_file)

svnrepos = Array(ASF::Config.get(:svn))

_html do
  _link rel: 'stylesheet', href: 'css/status.css'
  _img.logo src: '../whimsy.svg'
  _style %{
    td:nth-child(2), th:nth-child(2) {display: none}
    @media screen and (min-width: 1200px) {
       td:nth-child(2), th:nth-child(2) {display: table-cell}
    }
  }

  # remains true if all local checkouts are writable
  writable = true
  svnroot = (svnrepos.length == 1 && svnrepos.first =~ /^(\/\w[-.\w]*)+\/\*$/ &&
    File.writable?(svnrepos.first.chomp('*').untaint))

  _h1_ 'SVN Repository Status'

  _table_.table do
    _thead do
      _tr do
        _th 'repository'
        _th 'local path'
        _th 'local revision'
        _th 'server revision'
      end
    end

    _tbody do
      repository[:svn].values.sort_by {|value| value['url']}.each do |svn|
        local = ASF::SVN.find(svn['url']) unless svn['url'] =~ /^https?:/

        color = nil

        if local
          rev = `svn info #{local}`[/^Revision: (.*)/, 1]
          writable &&= File.writable?(local)
        else
          color = 'bg-danger'
        end

        _tr_ class: color do
          _td! title: local do
            _a svn['url'], href: "https://svn.apache.org/repos/#{svn['url']}"
          end

          _td local

          _td rev

          if local
            _td '(loading)'
          else
            _td
          end
        end
      end
    end
  end

  _script %{
    var writable = #{writable};
    var svnroot = #{!!svnroot};

    // update status of a row based on a sever response
    function updateStatus(tr, response) {
      var tds = $('td', tr);
      [1,2,3].forEach(function(i) {
         tds[i].textContent = '?' // show response has arrived at least
      });
      if (response.path) tds[1].textContent = response.path;
      if (response.local) tds[2].textContent = response.local;
      if (response.server) tds[3].textContent = response.server;

      // update row color
      if (tds[2].textContent != tds[3].textContent) {
        tr.setAttribute('class', 'bg-warning');

        if (writable) {
          $(tds[4]).html('<button class="btn btn-info">update</button>');
          $('button', tr).on('click', sendRequest);
        }
      } else {
        tr.setAttribute('class', 'bg-success');
        if (writable) $(tds[4]).empty();
      }
    };

    // when running locally, add a fourth column, and create a function
    // used to send requests to the server
    if (writable) {
      $('thead tr').append('<th>action</th');
      $('tbody tr').append('<td></td');

      function sendRequest(event) {
        var tr = event.currentTarget.parentNode.parentNode;
        var action = event.currentTarget.textContent;
        var tds = $('td', tr);
        var name = tds[0].textContent;
        event.currentTarget.disabled = true;
        $.getJSON('?action=' + action + '&name=' + name, function(response) {
          updateStatus(tr, response);
          event.currentTarget.disabled = false;
          updateAll();
        });
      }

      // add checkout buttons
      if (svnroot) {
        $('tbody tr').each(function(index, tr) {
          var tds = $('td', tr);
          var path = tds[0].getAttribute('title');
          if (tds[2].textContent == '') {
            $(tds[4]).html('<button class="btn btn-success">checkout</button>');
            $('button', tr).on('click', sendRequest);
          }
        })
      };
    }

    // fetch server revision for each row
    function updateAll() {
      $('tbody tr').each(function(index, tr) {
        var tds = $('td', tr);
        var path = tds[0].getAttribute('title');
        if (tds[2].textContent != '') {
          $.getJSON('?name=' + tds[0].textContent, function(response) {
            updateStatus(tr, response);
          });
        }
      });
    }

    updateAll();
  }
end

# process XMLHttpRequests
_json do
  local_path = ASF::SVN.find(@name.untaint)
  if local_path
    if @action == 'update'
      log = `svn cleanup #{local_path.untaint} 2>&1`
      log = log + `svn update #{local_path.untaint} 2>&1`
    end

    repository_url = ASF::SVN.getInfo(local_path)[/^URL: (.*)/, 1]

  else
    if @action == 'checkout'

      repo = repository[:svn].find {|name, value| value['url'] == @name}
      local_path = svnrepos.first.chomp('*') + repo.first

      repository_url = @name
      unless repository_url =~ /^https?:/
        repository_url = "https://svn.apache.org/repos/#{repository_url}"
      end

      log = `svn checkout #{repository_url.untaint} #{local_path.untaint} 2>&1`
    end
  end

  localrev, lerr = ASF::SVN.getRevision(local_path.untaint)
  serverrev, serr = ASF::SVN.getRevision(repository_url.untaint)
  {
    log: log.to_s.split("\n"),
    path: local_path,
    local: localrev || lerr.split("\n").last, # generally the last SVN error line is the cause
    server: serverrev || serr.split("\n").last
  }
end

# standalone (local) support
if __FILE__ == $0 and not ENV['GATEWAY_INTERFACE']
  require 'wunderbar/sinatra'

  get '/whimsy.svg' do
    send_file File.expand_path('../../whimsy.svg', __FILE__)
  end

  get '/css/status.css' do
    send_file File.expand_path('../css/status.css', __FILE__)
  end
end
